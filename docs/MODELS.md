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

## Public verified versus local experimental entries

Only `qwen-coder-q4` and `qwen35-q4` are currently `ready`. The other registry
entries are retained as `partial` records of local OpenClaw integration work:

| Alias | Purpose / evidence boundary |
| --- | --- |
| `qwen3-4b-q4` | Load, health, discovery, short generation, and OpenClaw request-start evidence |
| `qwen3-8b-q4` | Standalone OpenClaw integration; no full Argo Forge workflow |
| `qwen38-27b-q4` | Experimental human-evaluation setup |
| `qwen35-9b-q4` | Experimental OpenClaw integration |
| `qwen3-14b-q3` | Infrastructure and minimal transport validation |
| `qwen3-14b-q2` | Current OpenClaw AMS CPU-only integration and batch validation |

These entries use portable model filenames, contain no weights, and do not
claim that every user should obtain or run those models. Availability,
licensing, packing compatibility, and performance must be reviewed separately.

The `qwen3-14b-q2` entry remains `partial`; Goal 5L did not run the complete
ready criterion. Its `server_args` deliberately set logical
`--batch-size 256` and physical `--ubatch-size 128`. A controlled OpenClaw AMS
Goal 5K sweep on the reference Ivy Bridge host found this pair preserved prompt
throughput while materially improving cancellation responsiveness compared
with llama.cpp's 2048/512 defaults. Goal 5L subsequently verified that the
normal managed container receives both flags, loads the configured Q2_K model,
answers a small direct request, stays bound to host loopback, and is reachable
through the expected SSH transport path.

These values are specific to this model, pinned runtime, host, and integration
evidence. They are not Argo Forge-wide defaults and should not be copied to
other registry entries without measurement.

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
