#!/usr/bin/env python3
"""One CPU-only LFM2.5 server shared by llama.cpp Web UI and OpenCode."""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
MODEL = Path('/home/sergio/llama-cpp-models/LFM2.5-24B-A2B-Q4_K_M.gguf')
IMAGE = 'local/llama-cpp-lfm25:latest'
CONTAINER = 'argo-forge-lfm25'
BASE_URL = 'http://127.0.0.1:18080'
CONTEXT = 131072
OPENCODE_DIR = ROOT / 'opencode-local'

class LocalCodeError(Exception):
    pass

def positive_integer(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('must be a positive integer') from exc
    if number <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return number

def inspect(name=CONTAINER):
    result = subprocess.run(['docker', 'container', 'inspect', name], capture_output=True, text=True)
    if result.returncode:
        # Distinguish an absent container from a daemon/permission failure.
        subprocess.run(['docker', 'info'], check=True, stdout=subprocess.DEVNULL)
        if 'No such' in result.stderr:
            return None
        raise LocalCodeError(result.stderr.strip())
    return json.loads(result.stdout)[0]

def docker_inspect(fmt):
    result = subprocess.run(['docker', 'inspect', '--format', fmt, CONTAINER], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None

def server_command():
    return ['docker', 'run', '-d', '--init', '--name', CONTAINER,
            '--label', 'localcode.managed=true',
            '--log-opt', 'max-size=10m', '--log-opt', 'max-file=2',
            '-p', '127.0.0.1:18080:8080', '--mount',
            f'type=bind,source={MODEL},target=/models/lfm25.gguf,readonly',
            IMAGE, '--model', '/models/lfm25.gguf', '--host', '0.0.0.0',
            '--port', '8080', '--threads', '2', '--threads-batch', '2',
            '--ctx-size', str(CONTEXT), '--parallel', '1', '--n-gpu-layers', '0',
            '--jinja', '--metrics']

def managed():
    state = inspect()
    if state and (state['Config'].get('Labels') or {}).get('localcode.managed') != 'true':
        raise LocalCodeError(f'{CONTAINER} is unmanaged; leaving it untouched')
    return state

def validate(state):
    expected = server_command()
    if state['Config']['Cmd'] != expected[expected.index(IMAGE)+1:]:
        raise LocalCodeError('Existing container configuration differs; no automatic replacement')
    mounts = state['Mounts']
    if len(mounts) != 1 or mounts[0]['Source'] != str(MODEL) or mounts[0]['Destination'] != '/models/lfm25.gguf' or mounts[0]['RW']:
        raise LocalCodeError('Invalid model mount; leaving container untouched')
    if state['HostConfig']['PortBindings'] != {'8080/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18080'}]}:
        raise LocalCodeError('Unsafe port binding; leaving container untouched')
    image_id = subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip()
    if state['Image'] != image_id:
        raise LocalCodeError('Image changed; container replacement requires explicit user action')

def ensure_server():
    # Refuse concurrent copies, including the pre-existing standalone deployment.
    running = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).splitlines()
    for name in running:
        if name == CONTAINER:
            continue
        other = inspect(name)
        if name in ('llama-cpp-lfm25', 'localcode-llama-server') or any(m.get('Source') == str(MODEL) for m in (other or {}).get('Mounts', [])):
            raise LocalCodeError(f'Another model container is running: {name}. Stop it explicitly first.')
    state = managed()
    if state:
        validate(state)
        if not state['State']['Running']:
            subprocess.run(['docker', 'start', CONTAINER], check=True)
    else:
        if not MODEL.is_file() or not os.access(MODEL, os.R_OK):
            raise LocalCodeError(f'GGUF unreadable: {MODEL}')
        subprocess.run(['docker', 'image', 'inspect', IMAGE], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(server_command(), check=True)
    wait_for_server()
def opencode_config(model_id, steps, output, auto_approve=False):
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": f"llama.cpp/{model_id}",
        "small_model": f"llama.cpp/{model_id}",
        "default_agent": "local-build",
        "enabled_providers": ["llama.cpp"],
        "provider": {"llama.cpp": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "LFM2.5 local",
            "options": {"baseURL": f"{BASE_URL}/v1", "headerTimeout": False, "timeout": False},
            "models": {model_id: {"name": "LFM2.5-24B-A2B Q4_K_M", "options": {"reasoning_budget": 0}, "limit": {"context": CONTEXT, "output": output}}},
        }},
        "agent": {
            "local-build": {
                "description": "Compact local coding agent using one project shell tool",
                "mode": "primary",
                "prompt": "Inspect relevant files before editing. Minimize tool calls by combining related inspections and shell operations; create files with one heredoc or equivalent, not many echo calls. Read compiler and test errors, continue after failures, and inspect important edits or git diff when useful. Rerun relevant tests, verify requested output files exist, and never claim completion before requested verification succeeds. Be concise.",
                "steps": steps,
                "tools": {"*": False, "shell": True},
                "permission": {"*": "deny", "shell": "allow" if auto_approve else "ask"},
            },
            "title": {"tools": {"*": False}, "permission": "deny"},
            "summary": {"tools": {"*": False}, "permission": "deny"},
            "compaction": {"tools": {"*": False}, "permission": "deny"},
        },
        "tools": {"*": False}, "permission": {"*": "deny"}, "mcp": {}, "plugin": [],
    }


def endpoint(path, timeout=2):
    with urlopen(BASE_URL + path, timeout=timeout) as response:
        return response.read().decode()


def wait_for_server(timeout=600):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if docker_inspect("{{.State.Running}}") != "true":
            logs = subprocess.run(["docker", "logs", "--tail", "80", CONTAINER], text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout
            raise LocalCodeError("llama-server stopped while loading:\n" + logs)
        try:
            payload = json.loads(endpoint("/health"))
            if isinstance(payload, dict) and payload.get("status") == "ok":
                return
        except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise LocalCodeError("Timeout in attesa di /health. Vedi: docker logs argo-forge-lfm25")


def actual_model_id():
    try:
        payload = json.loads(endpoint("/v1/models", timeout=10))
        return payload["data"][0]["id"]
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise LocalCodeError(f"Could not get the model ID from /v1/models: {exc}") from exc



def launch(args):
    binary = os.environ.get('OPENCODE_BIN') or shutil.which('opencode')
    if not binary:
        candidate = OPENCODE_DIR / 'bin' / 'opencode'
        binary = str(candidate) if candidate.is_file() else None
    if not binary:
        raise LocalCodeError('OpenCode missing: see docs/INSTALLATION.md')
    if not (OPENCODE_DIR / 'node_modules/@opencode-ai/plugin').exists():
        raise LocalCodeError('Compact shell dependencies missing: see docs/INSTALLATION.md')
    config = opencode_config(actual_model_id(), args.steps, args.output, args.auto_approve)
    # Private config home prevents merging global providers, plugins and auth.
    with tempfile.TemporaryDirectory(prefix='argo-opencode-') as private:
        env = {k: v for k, v in os.environ.items() if not k.startswith('OPENCODE_')}
        env.update(XDG_CONFIG_HOME=private, OPENCODE_CONFIG_DIR=str(OPENCODE_DIR),
                   OPENCODE_CONFIG_CONTENT=json.dumps(config),
                   OPENCODE_DISABLE_PROJECT_CONFIG='true', OPENCODE_DISABLE_DEFAULT_PLUGINS='true',
                   OPENCODE_DISABLE_AUTOUPDATE='true', OPENCODE_DISABLE_MODELS_FETCH='true',
                   OPENCODE_DISABLE_SHARE='true')
        command = [binary, 'run', '--title', 'Argo Forge local task', '--agent', 'local-build', args.prompt] if args.prompt else [binary, str(Path.cwd()), '--agent', 'local-build']
        return subprocess.run(command, env=env).returncode

def main():
    p = argparse.ArgumentParser(description='LFM2.5 only; CPU; fixed 131072 context. No model/context selector.')
    p.add_argument('command', nargs='?', default='code', choices=['start', 'stop', 'restart', 'status', 'logs', 'stats', 'code', 'dry-run'])
    p.add_argument('--steps', type=positive_integer, default=24)
    p.add_argument('--output', type=positive_integer, default=256)
    p.add_argument('--prompt', help='Run one noninteractive OpenCode task')
    p.add_argument('--auto-approve', action='store_true', help='Explicitly allow shell commands without individual approval')
    args = p.parse_args()
    if args.command == 'dry-run':
        print(shlex.join(server_command())); return 0
    if args.command == 'status':
        state = managed()
        print('absent' if state is None else state['State']['Status'])
        if state:
            validate(state)
        print(f'Web UI: {BASE_URL}; context={CONTEXT}; CPU only'); return 0
    if args.command in ('stop', 'logs', 'restart'):
        state = managed()
        if not state:
            raise LocalCodeError('No managed container exists')
        if args.command == 'logs':
            return subprocess.run(['docker', 'logs', '--follow', '--tail', '100', CONTAINER]).returncode
        if args.command == 'stop':
            return subprocess.run(['docker', 'stop', CONTAINER]).returncode
        validate(state)
        subprocess.run(['docker', 'stop', CONTAINER], check=True)
    if args.command == 'stats':
        print(endpoint('/metrics', timeout=10)); return 0
    ensure_server()
    print(f'Web UI: {BASE_URL}; API: {BASE_URL}/v1; context={CONTEXT}')
    return launch(args) if args.command == 'code' else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (LocalCodeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'localcode: {exc}', file=sys.stderr)
        sys.exit(2)
