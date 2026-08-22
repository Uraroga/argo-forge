# Agent maintenance guide

## Mission

Argo Forge explores whether useful modern coding-agent loops can run locally on
old CPU-only hardware. OpenCode is the agent harness, llama.cpp serves one
interchangeable GGUF, and LocalCode connects them with a compact tool schema.

Maintain reproducibility and the old-CPU baseline before pursuing speed.

## Architecture

```text
localcode → models.json → Docker llama-server → read-only GGUF
          → localhost OpenAI endpoint → OpenCode → compact shell tool
          → current working repository
```

Model lifecycle and OpenCode are deliberately separated. LocalCode generates
the local-only OpenCode configuration in memory and preserves the invoking
directory as the workspace.

## Important files

- `localcode.py`: CLI, registry loading, managed-container lifecycle, health
  retries, model-ID discovery, and in-memory OpenCode configuration.
- `models.json`: model aliases, files, runtime, reasoning settings, extra server
  arguments, evidence status, and notes.
- `Dockerfile`: reproducible CPU-only llama.cpp build pinned to an exact commit
  and compiled for Ivy Bridge without AVX2/FMA assumptions.
- `opencode-local/package.json` and `package-lock.json`: pinned compact-tool
  dependency. Never commit `node_modules`.
- `opencode-local/tools/shell.ts`: the only enabled coding tool.
- `README.md` and `docs/`: public architecture, installation, model evidence,
  benchmark methodology, caveats, and troubleshooting.

## Safety invariants

Preserve all of these:

- Bind the host endpoint only to `127.0.0.1`.
- Keep CPU-only execution as the default.
- Mount exactly one selected GGUF and mount it read-only.
- Keep only one LocalCode model container at a time.
- Remove only the named container carrying `localcode.managed=true`.
- Never silently enable cloud LLM providers or default plugins.
- Keep model weights outside the repository and Docker image.
- Do not commit credentials, auth state, cookies, or session logs.
- Preserve the Ivy Bridge runtime baseline: no AVX2 or FMA assumption.
- Preserve retries for transient startup URL, timeout, connection-reset, and
  malformed early JSON responses.
- Keep the active source repository as the OpenCode workspace.
- Do not increase the tool schema casually. Argo Forge intentionally trades
  tool variety for small context overhead.

The compact shell tool executes as the current user and is not a security
sandbox. Do not describe it as one.

## Model-ready criterion

A model is `ready` only after this exact evidence chain succeeds:

```text
load
→ health
→ generation
→ OpenCode
→ real tool call
→ real file edit
→ post-edit test execution
→ green PASS
```

Loading, text generation, a syntactic tool call, or a correct edit without a
post-edit green test is insufficient. Use `partial`, `unverified`, or
`load-failed` and explain the exact boundary.

## Adding a model

1. Confirm the user supplied or authorized the GGUF; never download large
   weights implicitly.
2. Keep it in the external `models_dir`.
3. Add one clean registry entry without changing `localcode.py`.
4. Dry-run and verify localhost binding, read-only mount, CPU flags, and image.
5. Perform the smallest staged test: load, health, model ID, short generation,
   then a tiny reproducible agentic edit only if appropriate.
6. Stop the managed server between models and at the end.
7. Update status only to the evidence level actually reached.

## Testing discipline

Prefer syntax checks, JSON validation, dry runs, and small smoke projects.
Benchmarks are expensive on the reference host and must not be repeated without
a concrete question. Use identical prompts/settings for comparisons, label
single runs as exploratory, and separate load, generation, tool, edit, test,
and complete-agent stages.

## Execution budgets

`localcode MODEL --ctx N --steps N --output N` configures three independent
positive-integer budgets. Context defaults to the selected registry entry;
agent steps default to 24; model output per turn defaults to 256. OpenCode owns
the agent loop—do not add a second loop engine.

Large contexts cost RAM and prompt-processing time. Large step budgets can
produce hours-long CPU workloads. Keep defaults conservative and never silently
change them to huge values. Preserve the compact prompt's guidance to inspect
before editing, batch related shell operations, read errors, and verify with
relevant tests before claiming completion.

## Never do these things

- Do not commit GGUF, safetensors, model caches, Docker exports, or archives.
- Do not commit credentials, personal auth files, or raw private sessions.
- Do not read, modify, or publish `~/.codex`.
- Do not assume AVX2/FMA or remove old-CPU compatibility for performance.
- Do not mark a model `ready` without the complete criterion above.
- Do not silently enable cloud inference.
- Do not perform destructive cleanup outside this repository.
- Do not overwrite, force-push, or repurpose an unrelated GitHub repository.
- Do not run broad benchmarks or download huge models automatically.
