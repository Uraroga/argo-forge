# Models and registry

Argo Forge remains an interchangeable-model architecture. `models.json`
contains the currently public verified configurations; `localcode.py` has no
model-specific alias table.

GGUF weights stay outside the repository in `models_dir`. Environment variables
and `~` are expanded; the public default is `$HOME/llama-cpp-models`.

## Registry fields

| Field | Meaning |
| --- | --- |
| `alias` | Stable command-line name used as `localcode ALIAS` |
| `name` | Human-readable display name |
| `file` | GGUF filename relative to `models_dir` |
| `context` | Default context window |
| `runtime` | Docker image containing the compatible llama-server |
| `reasoning` | `off` disables runtime reasoning; other values preserve defaults |
| `server_args` | Extra llama-server arguments appended verbatim |
| `status` | Evidence status |
| `note` | Concise description of verified evidence |

## Ready criterion

A model is `ready` only after this complete evidence chain succeeds:

```text
load → health → generation → OpenCode → meaningful tool use
     → project inspection → real edit → post-edit test → green PASS
```

Loading, text generation, a syntactic tool call, or a correct-looking edit
without an executed green post-edit test is insufficient.

## Public verified models

### `qwen-coder-q4`

Qwen3-Coder-30B-A3B Q4_K_M completed the full Agent Benchmark v2 workflow and
executed `TEST PASS`. It produced the fastest successful agent run in this
single exploratory comparison.

### `qwen35-q4`

Qwen3.5-35B-A3B Q4_K_M completed the full Agent Benchmark v2 workflow and
executed `TEST PASS`. It used less measured container memory than
`qwen-coder-q4` in this run.

Both entries are `ready`. See [Agent Benchmark v2](BENCHMARKS.md) for the fixed
protocol, measurements, and caveats.

## Adding another local model

The public verified set is not a claim that other models cannot work. Users can
add compatible GGUF configurations themselves:

1. Obtain a GGUF from its publisher and review its license.
2. Store it outside this repository in `models_dir`.
3. Add one clean entry to `models.json`; do not change `localcode.py`.
4. Run `localcode ALIAS --dry-run` and inspect the image, read-only mount,
   localhost port, CPU flags, context, and budgets.
5. Test load, `/health`, `/v1/models`, and a small direct generation.
6. Keep the entry below `ready` until a real OpenCode edit followed by an
   executed green post-edit test succeeds.
7. Record only the evidence actually demonstrated.

Never commit model weights. A registry filename is metadata, not model
redistribution.
