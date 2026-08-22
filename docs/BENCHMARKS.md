# Argo Forge Agent Benchmark v2

## Scope

Argo Forge Agent Benchmark v2 is a small reproducible comparison of the public
model configurations that completed the full coding-agent workflow on the
reference machine. Each value below comes from one exploratory run.

These measurements are not statistically significant and should not be
interpreted as universal model rankings. Hardware, runtime, prompt, model
packing, and agent settings can materially change results.

## Environment

- Intel Core i3-3240 at 3.40 GHz
- 2 physical cores / 4 logical cores
- 32 GB RAM
- CPU-only
- Ubuntu 24.04.4 LTS
- Argo Forge commit `f9c2ace8b56e724bcbd04d3f14685406168eeda6`
- OpenCode 1.18.21
- pinned Ivy Bridge llama.cpp runtime

## Fixed protocol

Both models received identical conditions:

- context: 4096
- maximum agent steps: 16
- model output allowance: 512 tokens per turn
- CPU threads: 2
- one model and managed container at a time
- one fresh copy of the benchmark project per model
- one exploratory run per model

The project contained this bug:

```python
def is_even(n):
    return n % 2 == 1
```

The identical goal required the agent to inspect the project, fix the bug, run
the tests, continue until they passed, avoid unrelated files, and verify the
final result. A complete PASS required meaningful shell use, inspection, a real
edit, and an actually executed post-edit test printing `TEST PASS`.

Before the agent stage, each loaded model received the same small direct
generation request. Load time and agent wall time were measured externally;
prompt and generation throughput came from llama.cpp response timings. Memory
is the one-shot Docker container usage after load, so it is approximate rather
than a measured peak.

## Results

| Model | GGUF | Load time | Memory | Prompt tok/s | Generation tok/s | Agent wall time | Final result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Qwen3-Coder-30B-A3B Q4_K_M | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` | 63.5 s | 12.51 GiB | 6.23 | 4.57 | 522.5 s | `TEST PASS` |
| Qwen3.5-35B-A3B Q4_K_M | `Qwen3.5-35B-A3B-Q4_K_M.gguf` | 75.8 s | 7.92 GiB | 6.60 | 3.67 | 574.6 s | `TEST PASS` |

Both models completed load, generation capability, OpenCode execution,
meaningful compact-shell use, project inspection, the correct code edit, and a
green post-edit test.

In this particular exploratory comparison, Qwen3-Coder produced the fastest
successful agent run. Qwen3.5 used less measured container memory. These are
observations about these single runs on this machine, not universal performance
claims.

At the end of the campaign, the managed LocalCode server was stopped. Raw
laboratory logs remain outside the public repository.
