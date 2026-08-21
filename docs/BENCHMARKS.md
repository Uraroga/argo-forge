# Exploratory results on Intel Core i3-3240

## Scope and caveats

These are single exploratory runs on the Intel Core i3-3240 Ivy Bridge host.
They are
not statistically significant benchmarks, rankings, or reproducible estimates
for other hardware. No averages, warm/cold repetitions, confidence intervals,
or model-specific tuning were used.

All models used the existing CPU-only runtime
`local/qwen38-27b-server-ivybridge:dev`, context 2048, two inference threads,
one loaded model at a time, and the same local OpenCode `shell` tool.

## Normalized protocol

Generation prompt:

> Reply with exactly one short sentence explaining what a Python function is.

The generation request used `max_tokens=128` for every loadable model. This
was increased from the earlier 32-token exploratory run because 32 tokens cut
off reasoning models before a final answer. A completed HTTP response that
contained only reasoning is reported as partial generation, not as a usable
final answer.

The normalized agentic run used exactly the same settings for every loadable
model:

- context: 2048;
- timeout: 300 seconds;
- maximum agent steps: 8;
- model output allowance per turn: 512 tokens;
- prompt: `Inspect this small project, fix the bug, run the tests, and verify that they pass.`;
- workspace: `model-smoke`;
- initial implementation: `return n % 2 == 1`;
- test requirement: `is_even(4)` must return `True`;
- tool configuration: only the existing compact `shell` tool enabled.

Reasoning configuration was preserved from `models.json`: `default` for both
Bonsai models, Qwen-Coder, and Qwen3.5; `off` for Qwen3.8. Qwen3.8's
`--reasoning off` setting is the previously verified configuration and is the
only intentional model-specific protocol difference.

## Compatibility and agentic stages

| Model | Load | Generation | Tool call | File edit | Test execution | Complete agentic PASS |
| --- | --- | --- | --- | --- | --- | --- |
| Ternary Bonsai-27B Q2_0 | **FAIL** | N/A | N/A | N/A | N/A | **NO** |
| Bonsai-27B Q1_0 | PASS | Partial: API response, no final text | NO | NO | NO | **NO** |
| Qwen3-Coder-30B-A3B Q4_K_M | PASS | PASS | YES | YES | YES, green | **YES** |
| Qwen3.5-35B-A3B Q4_K_M | PASS | Partial: API response, no final text | YES | YES | YES, red before edit | **NO** |
| Qwen3.8-27B Q8_0 | PASS | PASS | NO in this run | NO in this run | NO in this run | **NO in this run** |

Stage definitions are deliberately strict. `Tool call` means OpenCode emitted
and executed the compact shell tool. `File edit` means the model actually
changed `math_utils.py`. `Test execution` records whether the model actually
ran the test; a red pre-edit run is distinguished from a green post-edit run.
Complete PASS requires reading the project, editing the file, running the test
after the edit, and obtaining PASS.

Qwen-Coder completed every required stage. It read both files, changed the
condition, tried `python`, retried with `python3`, and reached a green test.
OpenCode then reached the eight-step ceiling while preparing the concluding
text, after the operational success criteria had already been met.

Qwen3.5's result is partial and should not be described as a generic tool-call
failure. It listed and read the project, ran the broken test, and correctly
edited `n % 2 == 1` to `n % 2 == 0`. The 300-second timeout expired before it
reran the test after the edit, so it is not a complete agentic PASS.

Qwen3.8 made no tool call in this one normalized, time-limited run. This does
not revoke or replace its earlier verified end-to-end status: it remains
`ready` in the registry based on the prior successful verification.

## Single-run measurements

Memory is reported consistently as the resident set size of the
`llama-server` process from `docker top`, sampled after load. This includes
mmap-resident model pages more reliably than Docker working-set figures. RSS
is still only a point-in-time observation, not a peak measurement.

| Model | Approx. load | Process RSS | Prompt tok/s | Generation tok/s | Request wall time | Usable final answer |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ternary Bonsai-27B Q2_0 | failed in <1 s | N/A | N/A | N/A | N/A | N/A |
| Bonsai-27B Q1_0 | ~24 s | 4.37 GiB | 0.69 | 0.60 | 244.38 s | NO; hit 128-token limit in reasoning |
| Qwen3-Coder-30B-A3B Q4_K_M | ~55 s | 17.53 GiB | 7.29 | 5.24 | 7.47 s | YES |
| Qwen3.5-35B-A3B Q4_K_M | ~74 s | 20.91 GiB | 6.59 | 3.89 | 36.13 s | NO; hit 128-token limit in reasoning |
| Qwen3.8-27B Q8_0 | ~103 s | 27.40 GiB | 0.91 | 0.63 | 61.12 s | YES |

Every number in this table comes from one run only. Load time is taken from
the server timestamps (rounded); request wall time and llama.cpp timings are
from the same single generation request. They should not be interpreted as
stable throughput or statistically meaningful differences.

## Ternary Bonsai Q2_0 load failure

The 7,165,121,600-byte file was added to `models.json` as `bonsai-q2`, but the
current runtime cannot load it. The precise llama.cpp error is:

```text
gguf_init_from_reader: tensor 'output_norm.weight' has offset 337715200, expected 357580800
gguf_init_from_reader: failed to read tensor data
llama_model_load: error loading model
```

Because the model never reached `/health`, generation and agentic stages were
not attempted. No runtime rebuild, GGUF conversion, replacement download, or
infrastructure workaround was performed. The registry marks it `load-failed`.

## Conservative conclusion

In this single exploratory comparison on the Intel Core i3-3240,
Qwen3-Coder-30B-A3B Q4_K_M provided the strongest practical result, completing
the full coding task and producing the fastest usable short response among the
tested models. This is not a universal model ranking. Bonsai Q1
had the lowest observed RSS but was too slow to reach a useful final response
or tool call within the limits. Qwen3.5 showed meaningful partial agentic
ability but did not close the verification loop. Qwen3.8 remains the known
end-to-end baseline, despite timing out in this later constrained comparison.

At the end of the run, the broken workspace was restored and
`localcode --status` reported `LocalCode server: stopped`.
