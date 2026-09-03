# Argo Forge

Argo Forge is a CPU-only local coding-agent environment built from
[OpenCode](https://opencode.ai/), [llama.cpp](https://github.com/ggml-org/llama.cpp),
and interchangeable GGUF models. It demonstrates that a complete modern
coding-agent loop can run locally on modest hardware, including a 2012 Intel
Ivy Bridge CPU.

OpenCode owns the agent loop, llama.cpp serves one selected local model, and
LocalCode connects them with a deliberately compact tool schema. No cloud model
provider is enabled.

## How it works

```text
Developer
   │
   ▼
localcode ──► models.json ──► Docker llama-server ──► read-only local GGUF
   │                                      │
   └──────────────────────────────► 127.0.0.1:8080
                                          │
                                          ▼
                                      OpenCode
                                          │
                                          ▼
                                one compact shell tool
                                          │
                                          ▼
                                current source repository
```

LocalCode starts one managed CPU-only container, mounts exactly one external
GGUF read-only, waits for health, discovers the runtime model ID, and launches
OpenCode in the directory from which `localcode` was invoked.

The single shell tool keeps schema and prompt overhead small. It supports
inspection, edits, builds, and tests, returns separate stdout, stderr, and exit
code observations, and encourages batching related commands.

## Reference system

- Intel Core i3-3240 at 3.40 GHz (Ivy Bridge, 2012)
- HP Elite 8300 SFF reference host
- 2 physical cores / 4 threads
- 32 GB DDR3
- AVX and F16C; no AVX2 or FMA
- CPU-only
- Ubuntu 24.04 LTS

The Dockerfile pins llama.cpp and compiles release code with `-O3` and
`-march=ivybridge`: AVX and F16C are enabled; AVX2, FMA, BMI/BMI2, AVX-512,
AMX, CUDA, Vulkan, and OpenCL are disabled. This is tested hardware, not a
universal minimum.

## Features

- Interactive model selection and an extensible JSON registry
- Configurable context, output, and agent-step budgets
- One model container at a time
- Localhost-only OpenAI-compatible endpoint
- CPU-only execution and read-only GGUF mounts
- Current-directory workspace preservation
- Cloud providers and default plugins disabled
- One compact project shell tool
- Status, stop, server-only, and dry-run commands

## Quick start

```bash
localcode                 # interactive model and budget selection
localcode --list          # registered aliases, status, and default context
localcode qwen-coder-q4
localcode qwen35-q4
localcode --status
localcode --stop
```

## Agent budgets

LocalCode exposes three independent positive-integer controls:

- `--ctx N`: how much context the model can work with. Larger values cost RAM
  and prompt-processing time.
- `--output N`: maximum model output allowance for one turn. Default: 256.
- `--steps N`: maximum OpenCode agent iterations. Default: 24.

Examples are guidance, not universal optimum settings:

```bash
# Small bug fix
localcode qwen-coder-q4 --ctx 4096 --steps 24

# Iterative coding
localcode qwen-coder-q4 --ctx 8192 --steps 48 --output 1024

# Larger autonomous task
localcode qwen35-q4 --ctx 16384 --steps 100 --output 1024
```

Large step budgets can mean hours of autonomous CPU work. Start moderately and
increase `--steps` when the agent reaches `MAXIMUM STEPS REACHED` while still
making useful progress.

Dry runs validate a registry entry and print the complete configuration without
starting Docker or loading a model:

```bash
localcode qwen-coder-q4 --ctx 8192 --steps 48 --output 1024 --dry-run
```

## Verified and experimental models

Two public registry entries completed the full Argo Forge workflow on the
reference system:

| Alias | Model | Status |
| --- | --- | --- |
| `qwen-coder-q4` | Qwen3-Coder-30B-A3B Q4_K_M | `ready` |
| `qwen35-q4` | Qwen3.5-35B-A3B Q4_K_M | `ready` |

`ready` requires load, generation capability, OpenCode, meaningful shell-tool
use, project inspection, a real edit, and an executed green post-edit test.
The architecture remains model-interchangeable: users may add other compatible
local GGUF configurations through `models.json` and verify them independently.

The registry also contains `partial` local-integration entries used for
OpenClaw AMS experiments. They record reproducible filenames and launch
settings but have **not** completed Argo Forge's full edit-and-test criterion.
`localcode --list` shows the status of every entry; presence in the registry is
not a performance or readiness endorsement.

## OpenClaw AMS CPU-inference integration

The experimental `qwen3-14b-q2` entry serves Qwen3 14B Q2_K with context
16,384, two generation threads, two batch threads, mmap, reasoning off, one
slot, logical batch 256, and physical batch 128. OpenClaw AMS measured the
batch choice directly on the reference Ivy Bridge host: prompt-throughput
differences across tested batches were sub-percent and treated as noise, while
256/128 reduced cancel-to-release by 87.462% against a historical 2048/512
observation.

That result is specific to one GGUF, pinned llama.cpp build, prompt, and host;
it is not a universal batch recommendation. Argo Forge still binds the managed
endpoint only to `127.0.0.1:8080`. See the
[OpenClaw AMS evidence](https://github.com/Uraroga/openclaw-ams/blob/main/docs/local-model-integration.md).

## Agent Benchmark v2

Argo Forge Agent Benchmark v2 used the same small reproducible Python bug-fix
task and a fresh workspace for each currently verified model. Both executed a
real post-edit `TEST PASS`.

Fixed configuration:

- context: 4096
- steps: 16
- output: 512
- CPU threads: 2

These are single exploratory runs, not statistically significant measurements
or universal rankings. In this comparison, `qwen-coder-q4` produced the fastest
successful agent run, while `qwen35-q4` had lower measured memory usage. See
[Agent Benchmark v2](docs/BENCHMARKS.md) for methodology and measurements.

## Installation

Install Docker, Python, Git, OpenCode, and Node/npm; build the pinned runtime;
keep legally obtained GGUF weights outside the repository; install the locked
compact-tool dependency; and link `localcode.py` onto `PATH`.

See [Installation](docs/INSTALLATION.md) for exact commands.

## Documentation

- [Installation](docs/INSTALLATION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Models and registry](docs/MODELS.md)
- [Agent Benchmark v2](docs/BENCHMARKS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Agent maintenance guide](AGENTS.md)

## Limitations

The current setup is text-only and cannot visually inspect a graphical
application. Measurements on the reference host are exploratory and should not
be extrapolated to other CPUs, GPUs, runtimes, prompts, or GGUF packings.
Local inference on two old CPU cores is slow, and full agent runs may take many
minutes or hours. The compact shell tool executes as the current user; it is an
overhead reduction, not a security sandbox.

## License

Original Argo Forge code and documentation are licensed under the
[MIT License](LICENSE). Model weights, llama.cpp, OpenCode, npm packages, and
other third-party components retain their own licenses.
