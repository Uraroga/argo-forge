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
DEFAULT_STEPS = 24
DEFAULT_OUTPUT = 256
CPU_THREADS = 2


class LocalCodeError(Exception):
    pass


def positive_integer(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


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
        epilog=f"""Execution budgets:
  Context (--ctx)    How much information the model can keep available.
                     Larger values cost more RAM and prompt-processing time.
  Steps (--steps)    Maximum agent actions OpenCode can perform before stopping.
  Output (--output)  Maximum model output allowance for one turn.

Guidance (not universal optimum values):
  Small bug fix:                  --ctx 4096 or 8192 --steps 24
  Small application / iteration: --ctx 8192 --steps 48
  Larger autonomous task:        --ctx 8192 or 16384 --steps 100

Start with a moderate step budget. Increase it when the agent reaches
MAXIMUM STEPS REACHED while it is still making useful progress. Many steps can
mean hours of autonomous work on an old CPU.

Examples:
  localcode                         interactive model selector
  localcode --list                  list models and status
  localcode qwen-coder-q4           server + OpenCode
  localcode qwen-coder-q4 --ctx 8192 --steps 48 --output 1024
  localcode qwen35-q4 --ctx 4096 --dry-run
  localcode qwen35-q4 --server-only
  localcode --status
  localcode --stop

Normally LocalCode starts llama-server and then OpenCode in the current project.
--server-only starts only the server; --stop removes only the managed container.
GGUF files are read from the models_dir configured in models.json and inference
runs locally on the CPU. No cloud LLM provider is enabled.""",
    )
    p.add_argument("model", nargs="?", help="model alias (see --list)")
    p.add_argument("--ctx", type=positive_integer, metavar="N",
                   help="context window (default: selected model's registry value)")
    p.add_argument("--steps", type=positive_integer, metavar="N",
                   help=f"maximum OpenCode agent steps (default: {DEFAULT_STEPS})")
    p.add_argument("--output", type=positive_integer, metavar="N",
                   help=f"maximum model output tokens per turn (default: {DEFAULT_OUTPUT})")
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
    alias = docker_inspect('{{ index .Config.Labels "localcode.model" }}') or "unknown"
    ctx = docker_inspect('{{ index .Config.Labels "localcode.context" }}') or "unknown"
    steps = docker_inspect('{{ index .Config.Labels "localcode.steps" }}') or "unknown"
    output = docker_inspect('{{ index .Config.Labels "localcode.output" }}') or "unknown"
    print(f"LocalCode server: {state}; model={alias}; context={ctx}; steps={steps}; "
          f"output={output}; endpoint={BASE_URL}/v1")


def prompt_budget(label, default):
    try:
        raw = input(f"{label} [{default}]: ").strip()
        value = int(raw) if raw else default
    except (EOFError, ValueError) as exc:
        raise LocalCodeError(f"Invalid {label.lower()}: enter a positive integer.") from exc
    if value <= 0:
        raise LocalCodeError(f"Invalid {label.lower()}: enter a positive integer.")
    return value


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
    ctx = prompt_budget("Context", model["context"])
    steps = prompt_budget("Agent steps", DEFAULT_STEPS)
    output = prompt_budget("Output tokens", DEFAULT_OUTPUT)
    return model, ctx, steps, output


def server_command(model, model_path, ctx, steps, output):
    mounted = f"/models/{model_path.name}"
    cmd = [
        "docker", "run", "-d", "--init", "--name", CONTAINER,
        "--label", MANAGED_LABEL,
        "--label", f"localcode.model={model['alias']}",
        "--label", f"localcode.context={ctx}",
        "--label", f"localcode.steps={steps}",
        "--label", f"localcode.output={output}",
        "--label", f"localcode.runtime={model['runtime']}",
        "--log-opt", "max-size=10m", "--log-opt", "max-file=2",
        "-p", "127.0.0.1:8080:8080",
        "-v", f"{model_path}:{mounted}:ro",
        model["runtime"],
        "--model", mounted, "--host", "0.0.0.0", "--port", "8080",
        "--ctx-size", str(ctx), "--threads", str(CPU_THREADS),
        "--threads-batch", str(CPU_THREADS),
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


def opencode_config(model, model_id, ctx, steps, output):
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
            "models": {model_id: {"name": model["name"], "limit": {"context": ctx, "output": output}}},
        }},
        "agent": {
            "local-build": {
                "description": "Compact local coding agent using one project shell tool",
                "mode": "primary",
                "prompt": "Inspect relevant files before editing. Minimize tool calls by combining related inspections and shell operations; create files with one heredoc or equivalent, not many echo calls. Read compiler and test errors, continue after failures, and inspect important edits or git diff when useful. Rerun relevant tests, verify requested output files exist, and never claim completion before requested verification succeeds. Be concise.",
                "steps": steps,
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
        steps = args.steps if args.steps is not None else DEFAULT_STEPS
        output = args.output if args.output is not None else DEFAULT_OUTPUT
    else:
        budgets_given = any(value is not None for value in
                            (args.ctx, args.steps, args.output))
        if args.dry_run or args.server_only or budgets_given:
            raise LocalCodeError("Specify MODEL or run 'localcode' without options for the menu.")
        model, ctx, steps, output = choose_interactive(models)
    model_path = Path(os.path.expandvars(data["models_dir"])).expanduser() / model["file"]
    if not model_path.is_file() or not os.access(model_path, os.R_OK):
        raise LocalCodeError(f"GGUF does not exist or is unreadable: {model_path}")
    cmd = server_command(model, model_path, ctx, steps, output)
    print(f"Model: {model['name']} ({model['alias']}, {model['status']})")
    print(f"Context: {ctx}\nAgent steps: {steps}\nOutput tokens: {output}")
    print(f"CPU threads: {CPU_THREADS}\nRuntime: {model['runtime']}")
    print(f"Workspace: {Path.cwd()}\nGGUF: {model_path}")
    print("llama-server:", shlex.join(cmd))
    if args.dry_run:
        print("Model ID: <discovered from /v1/models after /health>")
        return 0
    if not OPENCODE.is_file():
        raise LocalCodeError(f"OpenCode not found: {OPENCODE}")
    if not (OPENCODE_DIR / "node_modules" / "@opencode-ai" / "plugin").exists():
        raise LocalCodeError(f"Tool dependencies missing from {OPENCODE_DIR}/node_modules")
    current = docker_inspect("{{.State.Running}}") == "true"
    same = (current and is_managed()
            and docker_inspect('{{ index .Config.Labels "localcode.model" }}') == model["alias"]
            and docker_inspect('{{ index .Config.Labels "localcode.context" }}') == str(ctx)
            and docker_inspect('{{ index .Config.Labels "localcode.steps" }}') == str(steps)
            and docker_inspect('{{ index .Config.Labels "localcode.output" }}') == str(output)
            and docker_inspect('{{ index .Config.Labels "localcode.runtime" }}') == model["runtime"])
    if not same:
        stop_server(quiet=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    print("Waiting for /health...")
    try:
        wait_for_server()
        model_id = actual_model_id()
    except LocalCodeError as exc:
        append_log([f"model={model['alias']}", f"gguf={model_path}",
                    f"ctx={ctx}", f"steps={steps}", f"output={output}",
                    f"runtime={model['runtime']}", f"command={shlex.join(cmd)}", f"error={exc}"])
        raise
    config = opencode_config(model, model_id, ctx, steps, output)
    config_json = json.dumps(config, separators=(",", ":"))
    append_log([f"model={model['alias']}", f"gguf={model_path}",
                f"ctx={ctx}", f"steps={steps}", f"output={output}",
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
