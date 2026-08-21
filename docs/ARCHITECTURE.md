# Architecture

Argo Forge separates model lifecycle management from coding-agent behavior.
The model is interchangeable; OpenCode remains the stable harness that owns
the task loop and workspace.

## Request flow

```text
localcode
   │
   ▼
models.json
   │
   ▼
Docker llama-server ──► read-only GGUF outside the repository
   │
   ▼
OpenAI-compatible endpoint on 127.0.0.1:8080
   │
   ▼
OpenCode with an in-memory local-only configuration
   │
   ▼
compact shell tool
   │
   ▼
the current working repository
```

## LocalCode launcher

`localcode.py` reads `models.json`, validates the selected alias and GGUF,
constructs the Docker command, and manages a container named
`localcode-llama-server`. Labels record ownership, model alias, context, and
runtime. LocalCode refuses to remove an identically named container without
its ownership label.

Only one model is loaded because the reference host has limited memory and
because deterministic model switching is easier to reason about than multiple
competing servers. When a different selection is launched, LocalCode replaces
only its own managed container.

The endpoint is published as `127.0.0.1:8080:8080`; it is not exposed on all
host interfaces. The single selected GGUF is mounted under `/models` with
`:ro`. Weights stay in `$HOME/llama-cpp-models`, outside both the repository
and Docker image.

## Startup and model discovery

Loading can take minutes. During that period llama-server may refuse or reset
health connections or briefly return incomplete data. LocalCode polls
`/health`, catches transient URL, timeout, connection, reset, and JSON parsing
errors, and continues while the managed container is alive. It does not assume
that a successful `docker run` means the model is ready.

After health becomes `ok`, LocalCode requests `/v1/models`. The returned model
ID is used to build the OpenCode provider configuration, avoiding assumptions
about how a runtime names the loaded model.

## OpenCode isolation

The generated OpenCode configuration exists only in process memory through
`OPENCODE_CONFIG_CONTENT`. It enables the `llama.cpp` provider at the localhost
endpoint, disables all cloud providers and default plugins, and points
`OPENCODE_CONFIG_DIR` at `opencode-local`.

The current shell directory is passed to OpenCode as the workspace. Argo Forge
does not add `.opencode` files to repositories visited by the user.

## Why one compact tool

OpenCode's broad default toolset is useful with large cloud contexts but its
schemas and agent instructions consume prompt tokens. At context 2048, that
overhead can crowd out the task and source code. On the Ivy Bridge host,
processing the tool-aware prompt can also dominate wall time before generation
begins.

Argo Forge disables every default tool and exposes one compact `shell` tool
with one string argument. It runs Bash in the active workspace and returns
stdout, stderr, and the exit code. This gives the model enough capability to
inspect, edit, compile, and test while keeping the schema small.

This is an engineering tradeoff, not a sandbox boundary. The tool executes as
the current user. Run untrusted models and tasks only in an appropriately
isolated environment.
