# Installation

This guide reproduces the first Argo Forge environment on Ubuntu. Commands use
portable home-relative paths; choose a different project directory if needed.

## Tested software and hardware

- Ubuntu 24.04 LTS
- Python 3.12 from Ubuntu
- Docker Engine
- OpenCode 1.18.20 for the verified agent runs
- `@opencode-ai/plugin` 1.18.20, pinned by `opencode-local/package-lock.json`
- llama.cpp commit `bb4caa7540188872173c44d161602d9271386413`
- Intel Core i3-3240, AVX/F16C, without AVX2/FMA

OpenCode may have newer releases. Version 1.18.20 is the tested reference, not
a claim that later versions are incompatible.

## 1. Prerequisites

Install Git, Python, Docker, Node.js, and npm using your preferred trusted
Ubuntu packages or upstream instructions. Confirm:

```bash
git --version
python3 --version
docker version
node --version
npm --version
```

Use a current Node.js release compatible with the engines declared by the
locked npm dependency tree. Ubuntu's older Node 18 can install the current lock
with engine warnings, but is not the recommended reproduction environment;
OpenCode itself executes the TypeScript tool with Bun.

Your user must be able to run Docker. Follow Docker's official post-install
guidance rather than making the daemon or socket world-writable.

Install OpenCode using its official instructions and verify the binary:

```bash
$HOME/.opencode/bin/opencode --version
```

If OpenCode is elsewhere, set `OPENCODE_BIN` to its executable path when
running LocalCode.

## 2. Clone Argo Forge

```bash
mkdir -p "$HOME/Progetti"
git clone https://github.com/Uraroga/argo-forge.git "$HOME/Progetti/argo-forge"
cd "$HOME/Progetti/argo-forge"
```

## 3. Build the CPU-only llama.cpp image

The Dockerfile clones and checks out the exact llama.cpp commit above. Its
compiler baseline deliberately avoids instructions unavailable on Ivy Bridge:

- `GGML_NATIVE=OFF`
- AVX and F16C enabled
- AVX2, FMA, BMI/BMI2, AVX-512, AMX, and GPU backends disabled
- compiler flags include `-march=ivybridge`, `-mno-avx2`, and `-mno-fma`

Build the historical runtime tag used by the registry:

```bash
docker build -t local/qwen38-27b-server-ivybridge:dev .
```

Despite the historical tag, the image contains a generic pinned
`llama-server` and is used by all current registry entries. To verify build
metadata without loading a model:

```bash
docker run --rm --entrypoint sh local/qwen38-27b-server-ivybridge:dev \
  -c 'cat /usr/local/share/llama-build-info.txt'
```

## 4. Install the compact OpenCode tool dependency

Dependencies are locked and are not committed as `node_modules`:

```bash
cd "$HOME/Progetti/argo-forge/opencode-local"
npm ci
cd ..
```

The tool source is `opencode-local/tools/shell.ts`. LocalCode points OpenCode
at this isolated configuration directory and disables default plugins.

## 5. Prepare model storage

Models stay outside Git:

```bash
mkdir -p "$HOME/llama-cpp-models"
```

Acquire GGUF weights directly from their publishers and review their licenses.
Argo Forge does not download weights. Put filenames in this directory exactly
as declared in `models.json`, or edit the registry to match files you legally
obtained.

The public registry uses:

```json
"models_dir": "$HOME/llama-cpp-models"
```

`localcode.py` expands environment variables and `~`. You can instead point to
a different registry with `LOCALCODE_REGISTRY=/path/to/models.json`.

## 6. Install the LocalCode command

```bash
mkdir -p "$HOME/.local/bin"
ln -s "$HOME/Progetti/argo-forge/localcode.py" "$HOME/.local/bin/localcode"
```

If the link already exists and you intend to replace that exact link:

```bash
ln -sfn "$HOME/Progetti/argo-forge/localcode.py" "$HOME/.local/bin/localcode"
```

Ensure `$HOME/.local/bin` is on `PATH`, then validate:

```bash
localcode --help
localcode --list
localcode qwen-coder-q4 --dry-run
```

The dry run checks the registry and GGUF path but does not load a model.

## 7. First real launch

Run LocalCode from the source repository you want the agent to edit:

```bash
cd "$HOME/Progetti/my-project"
localcode qwen-coder-q4
```

LocalCode loads the model, waits for health, and opens OpenCode with
`my-project` as its workspace. The first load can take a long time on old CPUs.

Inspect or stop the managed server:

```bash
localcode --status
localcode --stop
```

Only the container named `localcode-llama-server` with the ownership label
`localcode.managed=true` is removed by `--stop`.
