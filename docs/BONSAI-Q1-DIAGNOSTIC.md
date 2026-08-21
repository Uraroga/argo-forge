# Bonsai 27B Q1 targeted agentic diagnostic

Date: 2026-08-21. This is a narrow diagnostic, not a benchmark and not a
claim about Bonsai's behavior on other runtimes or hardware.

## Environment

- CPU: Intel Core i3-3240 at 3.40 GHz, 2 physical cores / 4 threads, x86_64.
- Runtime: `local/qwen38-27b-server-ivybridge:dev`, llama.cpp build
  `b10566-bb4caa754`, CPU-only.
- Model: `$HOME/llama-cpp-models/Bonsai-27B-Q1_0.gguf` on the historical test host.
- Context: 2048.
- Server threads: 2; batch threads: 2.
- Network: `127.0.0.1:8080` only.
- Model mount: single GGUF, read-only.

The pre-diagnostic `bonsai-q1` registry entry was:

```json
{
  "alias": "bonsai-q1",
  "name": "Bonsai-27B Q1_0",
  "file": "Bonsai-27B-Q1_0.gguf",
  "context": 2048,
  "runtime": "local/qwen38-27b-server-ivybridge:dev",
  "reasoning": "default",
  "server_args": [],
  "status": "unverified",
  "note": "Runtime provvisorio nel registry; compatibilita da verificare"
}
```

It was left unchanged because no tested Bonsai-specific configuration
demonstrated a better operational result.

## Reference configuration

PrismML's official Bonsai demo states that the 27B model uses `--jinja` for
native OpenAI-style tool calling and keeps thinking enabled. Its reference
server script uses:

```text
--temp 0.7 --top-p 0.95 --top-k 20 --min-p 0 --jinja
```

Sources:

- <https://github.com/PrismML-Eng/Bonsai-demo/blob/main/AGENTS.md>
- <https://github.com/PrismML-Eng/Bonsai-demo/blob/main/scripts/start_openwebui.sh>
- <https://huggingface.co/prism-ml/Bonsai-27B-gguf>

The installed llama-server help confirms support for `--jinja` and
`--reasoning-budget N`: `-1` is unrestricted, `0` forces an immediate end, and
positive values bound reasoning tokens. Upstream documentation:

- <https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md>
- <https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md>

Each diagnostic server used the following effective command shape, changing
only `N` between runs:

```text
llama-server
  --model /models/Bonsai-27B-Q1_0.gguf
  --host 0.0.0.0 --port 8080
  --ctx-size 2048
  --threads 2 --threads-batch 2
  --n-gpu-layers 0 --load-mode mmap
  --jinja
  --temp 0.7 --top-p 0.95 --top-k 20 --min-p 0
  --reasoning-budget N
```

Docker published the port only as `127.0.0.1:8080:8080` and mounted the GGUF
with `:ro`.

`/props` confirmed the reference sampling values and a tool-aware embedded
chat template. Its capabilities included `supports_tools: true` and
`supports_tool_calls: true`. The current runtime reports `--jinja` as enabled
by default; specifying it explicitly therefore verified the intended path but
did not necessarily introduce a difference from the earlier generic launch.

## Direct tool-call results

All runs used one no-argument OpenAI-schema function named
`get_magic_number`, `tool_choice: required`, and the same user prompt:

```text
Use the get_magic_number tool. Do not answer the question yourself.
```

Each non-streaming request had a 240-second wall timeout. This was deliberately
shorter than another unrestricted-reasoning experiment while still allowing
substantially more than the requested reasoning budgets at the previously
observed decode speed.

| Reasoning budget | Completed HTTP response | Reasoning observable | Final content | Native `tool_calls` | Time to tool call | Notes |
| ---: | --- | --- | --- | --- | ---: | --- |
| 64 | NO | Not observable | None | NO | >240 s | Server accepted and launched task; client timed out |
| 32 | NO | Not observable | None | NO | >240 s | Same result as 64 |
| 0 | NO | Not observable | None | NO | >240 s | Disabling reasoning did not make the request finish |

The server was healthy before each request. Logs showed the request assigned
to a slot and then cancelled exactly when the client timeout expired; no
completed response payload was returned. Because the requests were
non-streaming, it is not possible to claim that hidden partial reasoning was
or was not generated. There was no final content and no native `tool_calls`
object to inspect.

The lack of differentiation between budgets 64, 32, and 0 weakens the specific
hypothesis that unrestricted decoding-time reasoning was the only blocker.
The most plausible local bottleneck is tool-aware prompt processing: `--jinja`
adds the model's tool instructions and JSON schema, while this model previously
processed prompts at only about 0.69 tokens/s on this CPU. However, this is an
inference from the timing and logs, not a detailed profiling result. The logs
did not emit a completed prompt-evaluation timing before cancellation.

## Tool round-trip

**Not attempted.** No run produced a native tool call, so there was no valid
call ID or assistant tool-call message to return a fake result against.

## OpenCode coding test

**Not attempted**, as required by the diagnostic protocol. Direct native tool
calling was not demonstrated first. Therefore this diagnostic provides no new
OpenCode integration result and makes no claim about read/edit/test behavior
under these flags.

The existing `model-smoke` workspace was verified at the end to contain the
intentional bug:

```python
return n % 2 == 1
```

## Final interpretation

1. **Model load capability: PASS.** Bonsai Q1 loaded and `/health` became
   ready under all three Bonsai-specific configurations.
2. **Text generation capability: PASS from the earlier direct test.** The
   model is known to generate text, although it is very slow on this CPU.
3. **Native tool-calling capability: NOT DEMONSTRATED here.** The official
   tool-aware template was active, but none of the bounded requests completed
   or returned `tool_calls` within 240 seconds.
4. **OpenCode integration: NOT TESTED in this diagnostic.** The prerequisite
   direct native tool call did not pass.
5. **Complete coding-agent capability: NOT DEMONSTRATED on this host/config.**

The accurate scoped conclusion is: **Bonsai Q1 loads and generates
successfully, but native tool calling was not demonstrated on this Argo Forge
/ Ivy Bridge configuration.** This must not be generalized into a claim that
the Bonsai model cannot call tools elsewhere.

No reasoning budget was a winner: 64, 32, and 0 all timed out without a
completed response. Explicit `--jinja` exposed the expected tool-capable
template but did not produce an observable practical improvement within the
test window. The recommended registry status remains `unverified`; there is
not enough evidence for `partial` or `ready`, and no permanent server arguments
were added.

At completion, `model-smoke` was in the intentionally broken state,
`localcode --stop` was run, and `localcode --status` reported
`LocalCode server: stopped`. Nothing was published.
