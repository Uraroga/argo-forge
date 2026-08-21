# Models and registry

`models.json` is the only file normally required to add or change a model.
`localcode.py` contains no model-specific alias table.

## Registry fields

The root `models_dir` is the directory containing weights. Environment
variables and `~` are expanded. The public default is
`$HOME/llama-cpp-models`.

Each entry has these fields:

| Field | Meaning |
| --- | --- |
| `alias` | Stable command-line name used as `localcode ALIAS` |
| `name` | Human-readable display name |
| `file` | GGUF filename relative to `models_dir` |
| `context` | Default context window; 2048 for the first release |
| `runtime` | Docker image containing the compatible llama-server |
| `reasoning` | `off` adds `--reasoning off`; other values preserve runtime defaults |
| `server_args` | Additional llama-server arguments appended verbatim |
| `status` | Evidence level described below |
| `note` | Scoped explanation of what was observed |

## Status semantics

### `ready`

Verified through a useful complete coding-agent workflow:

```text
load → health → generation → OpenCode → tool call → real edit
     → post-edit test execution → green PASS
```

### `partial`

Important functionality was observed, but the complete coding loop was not
demonstrated. The note must state exactly where the run stopped.

### `unverified`

The file may load or generate, but the required complete behavior has not been
demonstrated. This is not a statement about model quality.

### `load-failed`

The exact tested GGUF/runtime pair failed before inference. This does not mean
that the model family, another packing, or a newer runtime is universally
incompatible.

## First-release registry

### `qwen-coder-q4` — `ready`

Qwen3-Coder-30B-A3B Q4_K_M completed the normalized Ivy Bridge workflow: load,
generation, project inspection, real edit, and a green post-edit Python test.

### `qwen38-q8` — `ready`

Qwen3.8-27B Q8_0 completed an earlier end-to-end coding verification. A later
300-second normalized comparison did not reach a tool call, but one constrained
timeout does not erase the earlier successful evidence.

### `qwen35-q4` — `partial`

Qwen3.5-35B-A3B Q4_K_M loaded, generated, called tools, inspected the project,
ran the failing test, and correctly fixed the bug. It timed out before rerunning
the test after the edit, so it is not `ready`.

### `bonsai-q1` — `unverified`

Bonsai-27B Q1_0 loads and generates with very low observed RSS. The official
tool-aware Jinja path and reasoning budgets 64, 32, and 0 were tested, but no
complete native `tool_calls` response was returned within the targeted
240-second limits. This does not establish that Bonsai cannot call tools on
other hardware or configurations.

### `bonsai-q2` — `load-failed`

The exact file `Ternary-Bonsai-27B-Q2_0.gguf` failed with an unexpected
`output_norm.weight` tensor offset and unreadable GGUF tensor data in the pinned
runtime. No conclusion is drawn about other Ternary Bonsai variants.

The separate Q2_g64 variant is not part of this release.

## Adding a model

1. Obtain the GGUF directly from its publisher and review its license.
2. Store it outside the repository in `models_dir`.
3. Add one entry to `models.json`; do not create aliases for every experiment.
4. Run `localcode ALIAS --dry-run` and inspect the image, mount, port, and args.
5. Test load, `/health`, `/v1/models`, and one short generation.
6. Keep status `unverified` until the complete OpenCode edit-and-green-test
   workflow succeeds.
7. Document model-specific flags and evidence in `note` and public docs.

Never commit model weights. A filename in the registry is metadata, not a
redistribution of the model.
