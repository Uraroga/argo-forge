#!/usr/bin/env python3
"""Argo Forge launcher: select one local GGUF and run it through OpenCode."""

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
REGISTRY = Path(os.environ.get("LOCALCODE_REGISTRY", ROOT / "models.json"))
OPENCODE_DIR = ROOT / "opencode-local"
OPENCODE = Path(os.environ.get("OPENCODE_BIN", Path.home() / ".opencode/bin/opencode")).expanduser()
CONTAINER = "localcode-llama-server"
MANAGED_LABEL = "localcode.managed=true"
LOG = ROOT / "logs" / "localcode.log"
BASE_URL = "http://127.0.0.1:8080"


class LocalCodeError(Exception):
    pass


def load_registry():
    try:
        data = json.loads(REGISTRY.read_text())
        models = data["models"]
        by_alias = {item["alias"]: item for item in models}
        if len(by_alias) != len(models):
            raise ValueError("alias duplicato")
        return data, models, by_alias
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise LocalCodeError(f"Invalid registry ({REGISTRY}): {exc}") from exc


def parser():
    p = argparse.ArgumentParser(
        prog="localcode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Argo Forge — CPU-only local coding agents with interchangeable models",
        epilog="""Examples:
  localcode                         interactive model selector
  localcode --list                  list models and status
  localcode qwen38-q8               server + OpenCode
  localcode qwen-coder-q4 --ctx 2048
  localcode bonsai-q1 --ctx 4096 --dry-run
  localcode qwen38-q8 --server-only
  localcode --status
  localcode --stop

Normally LocalCode starts llama-server and then OpenCode in the current project.
--server-only starts only the server; --stop removes only the managed container.
GGUF files are read from the models_dir configured in models.json and inference
runs locally on the CPU. No cloud LLM provider is enabled.""",
    )
    p.add_argument("model", nargs="?", help="model alias (see --list)")
    p.add_argument("--ctx", type=int, metavar="N", help="context window (registry default: 2048)")
    p.add_argument("--list", action="store_true", help="list models, status, and default context")
    p.add_argument("--dry-run", action="store_true", help="validate and print commands without starting anything")
    p.add_argument("--server-only", action="store_true", help="start llama-server without OpenCode")
    p.add_argument("--status", action="store_true", help="show LocalCode server status")
    p.add_argument("--stop", action="store_true", help="stop the managed LocalCode server")
    return p


def docker_inspect(fmt):
    result = subprocess.run(
        ["docker", "inspect", "--format", fmt, CONTAINER],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def is_managed():
    return docker_inspect('{{ index .Config.Labels "localcode.managed" }}') == "true"


def stop_server(quiet=False):
    exists = docker_inspect("{{.Name}}") is not None
    if not exists:
        if not quiet:
            print("No LocalCode server is present.")
        return
    if not is_managed():
        raise LocalCodeError(f"Container {CONTAINER} exists but is not managed by LocalCode; leaving it untouched.")
    subprocess.run(["docker", "rm", "-f", CONTAINER], check=True, stdout=subprocess.DEVNULL)
    if not quiet:
        print("LocalCode server stopped.")


def show_status():
    state = docker_inspect("{{.State.Status}}")
    if state is None:
        print("LocalCode server: stopped")
        return
    if not is_managed():
        print(f"LocalCode server: unavailable (name {CONTAINER} is used by an unmanaged container)")
        return
    alias = docker_inspect('{{ index .Config.Labels "localcode.model" }}') or "?"
    ctx = docker_inspect('{{ index .Config.Labels "localcode.context" }}') or "?"
    print(f"LocalCode server: {state}; model={alias}; ctx={ctx}; endpoint={BASE_URL}/v1")


def choose_interactive(models):
    print("Argo Forge — local coding agent\n\nChoose a model:\n")
    for index, model in enumerate(models, 1):
        print(f"{index}) {model['name']} [{model['status']}]")
    try:
        raw = input("\nModel: ").strip()
        index = int(raw)
        model = models[index - 1]
    except (ValueError, IndexError, EOFError):
        raise LocalCodeError("Invalid model selection.")
    try:
        raw_ctx = input(f"Context [{model['context']}]: ").strip()
        ctx = int(raw_ctx) if raw_ctx else model["context"]
    except (EOFError, ValueError) as exc:
        raise LocalCodeError("Invalid context: enter a positive integer.") from exc
    return model, ctx


def server_command(model, model_path, ctx):
    mounted = f"/models/{model_path.name}"
    cmd = [
        "docker", "run", "-d", "--init", "--name", CONTAINER,
        "--label", MANAGED_LABEL,
        "--label", f"localcode.model={model['alias']}",
        "--label", f"localcode.context={ctx}",
        "--label", f"localcode.runtime={model['runtime']}",
        "--log-opt", "max-size=10m", "--log-opt", "max-file=2",
        "-p", "127.0.0.1:8080:8080",
        "-v", f"{model_path}:{mounted}:ro",
        model["runtime"],
        "--model", mounted, "--host", "0.0.0.0", "--port", "8080",
        "--ctx-size", str(ctx), "--threads", "2", "--threads-batch", "2",
        "--n-gpu-layers", "0", "--load-mode", "mmap",
    ]
    if model.get("reasoning") == "off":
        cmd += ["--reasoning", "off"]
    cmd += [str(arg) for arg in model.get("server_args", [])]
    return cmd


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
            if payload.get("status") == "ok":
                return
        except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise LocalCodeError("Timeout in attesa di /health. Vedi: docker logs localcode-llama-server")


def actual_model_id():
    try:
        payload = json.loads(endpoint("/v1/models", timeout=10))
        return payload["data"][0]["id"]
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError, KeyError, IndexError) as exc:
        raise LocalCodeError(f"Could not get the model ID from /v1/models: {exc}") from exc


def opencode_config(model, model_id, ctx):
    return {
        "$schema": "https://opencode.ai/config.json",
        "model": f"llama.cpp/{model_id}",
        "small_model": f"llama.cpp/{model_id}",
        "default_agent": "local-build",
        "enabled_providers": ["llama.cpp"],
        "provider": {"llama.cpp": {
            "npm": "@ai-sdk/openai-compatible",
            "name": f"llama-server {model['name']} local",
            "options": {"baseURL": f"{BASE_URL}/v1", "headerTimeout": False, "timeout": False},
            "models": {model_id: {"name": model["name"], "limit": {"context": ctx, "output": 256}}},
        }},
        "agent": {
            "local-build": {
                "description": "Compact local coding agent using one project shell tool",
                "mode": "primary",
                "prompt": "Use shell to inspect, edit, compile, and test the current project. Read errors and continue until the task is complete. Be concise.",
                "steps": 8,
                "tools": {"*": False, "shell": True},
                "permission": {"*": "deny", "shell": "allow"},
            },
            "title": {"tools": {"*": False}, "permission": "deny"},
            "summary": {"tools": {"*": False}, "permission": "deny"},
            "compaction": {"tools": {"*": False}, "permission": "deny"},
        },
        "tools": {"*": False}, "permission": {"*": "deny"}, "mcp": {}, "plugin": [],
    }


def append_log(lines):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    if LOG.exists() and LOG.stat().st_size > 1_000_000:
        LOG.replace(LOG.with_suffix(".log.1"))
    with LOG.open("a") as handle:
        handle.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " | ".join(lines) + "\n")


def main():
    args = parser().parse_args()
    data, models, by_alias = load_registry()
    if args.list:
        print(f"{'ALIAS':<18} {'STATUS':<12} {'CTX':<6} MODEL")
        for model in models:
            print(f"{model['alias']:<18} {model['status']:<12} {model['context']:<6} {model['name']}")
        return 0
    if args.status:
        show_status(); return 0
    if args.stop:
        stop_server(); return 0
    if args.model:
        if args.model not in by_alias:
            raise LocalCodeError(f"Unknown model: {args.model}. Use 'localcode --list'.")
        model = by_alias[args.model]
        ctx = args.ctx if args.ctx is not None else model["context"]
    else:
        if args.dry_run or args.server_only or args.ctx is not None:
            raise LocalCodeError("Specify MODEL or run 'localcode' without options for the menu.")
        model, ctx = choose_interactive(models)
    if ctx <= 0:
        raise LocalCodeError("--ctx must be a positive integer.")
    model_path = Path(os.path.expandvars(data["models_dir"])).expanduser() / model["file"]
    if not model_path.is_file() or not os.access(model_path, os.R_OK):
        raise LocalCodeError(f"GGUF does not exist or is unreadable: {model_path}")
    cmd = server_command(model, model_path, ctx)
    print(f"Model: {model['name']} ({model['status']})")
    print(f"GGUF: {model_path}\nContext: {ctx}\nRuntime: {model['runtime']}")
    print("llama-server:", shlex.join(cmd))
    if args.dry_run:
        print("Model ID: <discovered from /v1/models after /health>")
        print(f"OpenCode workspace: {Path.cwd()}")
        return 0
    if not OPENCODE.is_file():
        raise LocalCodeError(f"OpenCode not found: {OPENCODE}")
    if not (OPENCODE_DIR / "node_modules" / "@opencode-ai" / "plugin").exists():
        raise LocalCodeError(f"Tool dependencies missing from {OPENCODE_DIR}/node_modules")
    current = docker_inspect("{{.State.Running}}") == "true"
    same = (current and is_managed()
            and docker_inspect('{{ index .Config.Labels "localcode.model" }}') == model["alias"]
            and docker_inspect('{{ index .Config.Labels "localcode.context" }}') == str(ctx)
            and docker_inspect('{{ index .Config.Labels "localcode.runtime" }}') == model["runtime"])
    if not same:
        stop_server(quiet=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    print("Waiting for /health...")
    try:
        wait_for_server()
        model_id = actual_model_id()
    except LocalCodeError as exc:
        append_log([f"model={model['alias']}", f"gguf={model_path}", f"ctx={ctx}",
                    f"runtime={model['runtime']}", f"command={shlex.join(cmd)}", f"error={exc}"])
        raise
    config = opencode_config(model, model_id, ctx)
    config_json = json.dumps(config, separators=(",", ":"))
    append_log([f"model={model['alias']}", f"gguf={model_path}", f"ctx={ctx}",
                f"runtime={model['runtime']}", f"command={shlex.join(cmd)}", f"model_id={model_id}"])
    print(f"Model ID: {model_id}")
    if args.server_only:
        print(f"Server ready at {BASE_URL}/v1")
        return 0
    env = os.environ.copy()
    env["OPENCODE_CONFIG_DIR"] = str(OPENCODE_DIR)
    env["OPENCODE_CONFIG_CONTENT"] = config_json
    env["OPENCODE_DISABLE_DEFAULT_PLUGINS"] = "true"
    print(f"Starting OpenCode in workspace: {Path.cwd()}")
    os.execvpe(str(OPENCODE), [str(OPENCODE), str(Path.cwd()), "--agent", "local-build"], env)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LocalCodeError as exc:
        print(f"localcode: error: {exc}", file=sys.stderr)
        sys.exit(2)
    except subprocess.CalledProcessError as exc:
        print(f"localcode: command failed ({exc.returncode}): {shlex.join(exc.cmd)}", file=sys.stderr)
        sys.exit(exc.returncode or 1)
