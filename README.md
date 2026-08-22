# Argo Forge

Argo Forge is a CPU-only local coding-agent environment that combines
[OpenCode](https://opencode.ai/), [llama.cpp](https://github.com/ggml-org/llama.cpp),
and interchangeable GGUF language models. It was built to explore whether
modern coding agents can remain useful on old commodity CPUs, including an
Intel Ivy Bridge processor from 2012.

The central question is simple:

> Can modern local coding agents remain useful on decade-old CPU-only hardware?

Argo Forge is more than a model launcher. OpenCode remains the agent harness,
while the selected local model acts as an interchangeable brain. The LocalCode
workflow does not require a cloud model: it creates an isolated OpenCode
configuration with only a local llama.cpp provider and one compact shell tool.

## How it works

```text
Developer
   │
   ▼
localcode ──► models.json ──► Docker llama-server ──► local GGUF
   │                                      │
   │                                      ▼
   └──────────────────────────────► 127.0.0.1:8080
                                          │
                                          ▼
                                      OpenCode
                                          │
                                          ▼
                                compact local shell tool
                                          │
                                          ▼
                                current source repository
```

LocalCode selects a registry entry, starts one managed CPU-only Docker
container, mounts exactly one GGUF read-only, waits for `/health`, discovers
the actual model ID through `/v1/models`, and starts OpenCode in the directory
from which `localcode` was invoked.

The compact tool is a core design choice. Default agent tool schemas and
system prompts can consume a large fraction of a 2048-token context before a
model sees the actual task. On a very old CPU, prompt processing can also take
longer than generation. Argo Forge therefore disables the default toolset and
offers one small project-scoped shell tool for inspection, edits, builds, and
tests. The agent is encouraged to batch related inspections and shell commands
so it receives useful textual observations without wasting agent steps.

## Reference hardware

The first public release was tested primarily on **argo3**:

- Intel Core i3-3240 at 3.40 GHz (Ivy Bridge, 2012)
- 2 physical cores / 4 threads
- 32 GB DDR3
- AVX and F16C; no AVX2 or FMA
- CPU-only
- Ubuntu 24.04 LTS

This is tested hardware, not a minimum requirement. The Dockerfile deliberately
targets Ivy Bridge and disables newer instruction sets, so it should also run
on compatible or newer x86-64 CPUs. Other operating systems, architectures,
modern CPUs, and GPUs were not validated for this release.

## Features

- Interactive model selector and direct aliases
- Extensible JSON model registry
- One model loaded at a time
- CPU-only Docker inference
- Localhost-only OpenAI-compatible endpoint
- Read-only, single-file GGUF mounts
- Managed container ownership labels
- Startup health checks tolerant of transient connection failures
- Runtime model-ID discovery
- Current-directory OpenCode workspace preservation
- Isolated local provider configuration with cloud providers disabled
- One compact local coding tool
- Configurable context, per-turn output, and agent-step budgets
- Status, stop, server-only, and dry-run commands

## Quick start

After installation:

```bash
localcode                 # choose a model interactively
localcode --list          # show aliases and verification status
localcode qwen-coder-q4   # start the verified coding model and OpenCode
localcode qwen38-q8       # start the Qwen3.8 baseline
localcode --status
localcode --stop
```

## Agent budgets

LocalCode exposes three separate controls while OpenCode continues to own the
agent loop:

- `--ctx N` controls how much context the model can work with. More context
  costs RAM and prompt-processing time.
- `--output N` controls the maximum model output allowance for one turn. The
  default is 256 tokens.
- `--steps N` controls how many agentic work iterations OpenCode may perform.
  The default is 24.

All accept positive integers. These are guidance, not universal optimum values:

```bash
# Small bug fix
localcode qwen-coder-q4 --ctx 4096 --steps 24

# Small application or iterative coding
localcode qwen-coder-q4 --ctx 8192 --steps 48

# Larger autonomous task
localcode qwen-coder-q4 --ctx 16384 --steps 100 --output 1024
```

Large contexts increase RAM use and prompt-processing time. Large step budgets
can mean hours of autonomous work on slow CPUs. Start with a moderate step
budget. Increase it when the agent reaches `MAXIMUM STEPS REACHED` while it is
still making useful progress.

Use `--dry-run` to validate a model entry and inspect the Docker command
without loading the model:

```bash
localcode qwen-coder-q4 --dry-run
```

## Installation

At a high level, install Docker, Python, Git, OpenCode, and Node/npm; clone the
repository; build the pinned llama.cpp image; place GGUF files outside the
repository; install the compact tool dependencies; and symlink `localcode.py`
into a directory on `PATH`.

See [Installation](docs/INSTALLATION.md) for exact commands, the pinned
llama.cpp commit, Ivy Bridge compiler settings, model layout, and first launch.

## Models

| Alias | Model | Status |
| --- | --- | --- |
| `qwen-coder-q4` | Qwen3-Coder-30B-A3B Q4_K_M | `ready` |
| `qwen38-q8` | Qwen3.8-27B Q8_0 | `ready` |
| `qwen35-q4` | Qwen3.5-35B-A3B Q4_K_M | `partial` |
| `bonsai-q1` | Bonsai-27B Q1_0 | `unverified` |
| `bonsai-q2` | Ternary Bonsai-27B Q2_0 | `load-failed` for this exact file/runtime pair |

Status describes observed agentic behavior, not model quality. A model is
`ready` only after a complete load → generation → tool → edit → post-edit green
test workflow. See [Models](docs/MODELS.md) for field definitions and scoped
notes.

## Exploratory results

In one normalized exploratory comparison on the Intel Core i3-3240,
Qwen3-Coder Q4 was the only model to complete the full coding task and produced
the fastest usable short response among the tested models. Qwen3.5 reached a
real edit but timed out before rerunning the test. Qwen3.8 remains a previously
verified end-to-end baseline even though a later constrained run timed out.
Bonsai Q1 loaded in about 4.37 GiB RSS but did not demonstrate native tool
calling within the targeted time limits.

These are single runs, not statistically significant measurements or universal
model rankings. Read [Exploratory benchmarks](docs/BENCHMARKS.md) and the
[Bonsai Q1 diagnostic](docs/BONSAI-Q1-DIAGNOSTIC.md) before drawing conclusions.

## What the experiment taught us

- Old CPUs can load and generate with modern local models.
- Fitting a model in RAM does not make it a practical coding agent.
- Tool-schema and chat-template processing can dominate runtime on old CPUs.
- Agent-harness overhead matters when the full context is only 2048 tokens.
- A compact tool schema can make the difference between a viable and an
  unusable local loop.
- GGUF packing support depends on the exact llama.cpp runtime.
- Loading and text generation are weaker evidence than a real edit followed by
  a green test.

## Limitations and future work

The reference host is extremely slow by current standards. Context was held at
2048, measurements were single exploratory runs, and compatibility was tested
only for the listed GGUF/runtime pairs. Results should not be extrapolated to
modern CPUs or GPUs.

Future updates may examine Haswell/AVX2 hardware, Bonsai Q1 on a faster CPU,
the separate Ternary Bonsai Q2_g64 build, and additional local coding models.
None of those results are part of this release.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Models and registry](docs/MODELS.md)
- [Exploratory benchmarks](docs/BENCHMARKS.md)
- [Bonsai Q1 diagnostic](docs/BONSAI-Q1-DIAGNOSTIC.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Agent maintenance guide](AGENTS.md)

## License

Original Argo Forge code and documentation are licensed under the
[MIT License](LICENSE). Model weights, llama.cpp, OpenCode, npm packages, and
all other third-party components retain their own licenses; the Argo Forge
license does not relicense them.
