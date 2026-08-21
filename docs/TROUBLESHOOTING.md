# Troubleshooting

## Server startup resets or refuses connections

`docker run` returns before llama-server has loaded the GGUF. During loading,
`/health` can refuse a connection, reset it, time out, or briefly yield data
that cannot yet be decoded as JSON.

LocalCode intentionally retries transient `URLError`, `TimeoutError`,
`ConnectionError` (including `ConnectionResetError`), and early JSON parsing
errors while the managed container remains alive. Do not remove this behavior
or treat the first reset as a fatal model failure.

Use:

```bash
localcode --status
docker logs --tail 80 localcode-llama-server
```

If the container exited, its logs should contain the actual model-load error.

## Illegal instruction on an older CPU

A llama.cpp binary compiled natively on a newer system may use AVX2, FMA,
BMI2, AVX-512, or other instructions absent from Ivy Bridge and crash with
`Illegal instruction`.

The provided Dockerfile sets `GGML_NATIVE=OFF`, targets `-march=ivybridge`,
enables AVX/F16C, and explicitly disables AVX2, FMA, BMI/BMI2, AVX-512, and
AMX. Preserve those choices for the reference image. A faster build for newer
hardware should use a separate image tag rather than silently raising the
baseline.

## A model fails to load

GGUF metadata, quantization packing, tensor layout, and architecture support
depend on the exact llama.cpp version. A valid model family does not guarantee
that every GGUF packing works with every runtime.

Check the exact filename and runtime, then inspect logs. Keep the conclusion
scoped to that pair. The first-release Ternary Bonsai Q2_0 file, for example,
failed on an unexpected tensor offset; this is not evidence that all Ternary
Bonsai files are invalid.

Do not rebuild, convert, or redownload models automatically during routine
diagnosis.

## Tool-aware requests are extremely slow

On the i3-3240, the model may process fewer than one prompt token per second.
Jinja chat templates, tool instructions, and JSON schemas can therefore spend
minutes in prompt evaluation before decoding starts. Reducing a reasoning
budget affects thinking generation but may not fix prompt-processing cost.

Distinguish prompt evaluation from generation using llama-server timing logs.
Use one minimal tool and a short prompt before involving a full agent harness.

## Context is too small

At context 2048, default OpenCode agents and their complete tool schemas may
leave too little space for the task and source files. Argo Forge uses one
compact shell tool and disables the default toolset for this reason.

Do not casually add tools or long system prompts. Measure the context cost and
keep model limits in sync with `models.json`.

## OpenCode or tool dependencies are missing

The default OpenCode binary path is `$HOME/.opencode/bin/opencode`. Override it
with `OPENCODE_BIN` if necessary. Install the locked tool dependencies with:

```bash
cd opencode-local
npm ci
```

LocalCode deliberately does not fall back to cloud inference when the local
provider or tool configuration is unavailable.
