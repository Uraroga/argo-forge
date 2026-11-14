# Agent maintenance guide

Argo Forge is dedicated exclusively to LFM2.5-24B-A2B Q4_K_M on argo3.
Do not reintroduce a model registry, selection menu, cloud inference or automatic
context reduction. The only GGUF is
`/home/sergio/llama-cpp-models/LFM2.5-24B-A2B-Q4_K_M.gguf`, external and read-only.
Context is always 131072; CPU-only, two threads, one slot. Preserve Ivy Bridge
AVX/F16C compatibility without AVX2/FMA/BMI2 assumptions.

Use the existing local image and preserve the external standalone project.
Do not delete existing containers/images without confirmation. The launcher
must never automatically remove containers; manage only its named container
with `localcode.managed=true`. Bind only 127.0.0.1; LAN access uses SSH tunneling.
Never read/modify/publish ~/.codex, download model weights, save credentials,
commit logs or sessions, use sudo or push without explicit authorization.

Keep OpenCode's invoking directory as workspace, only the compact shell enabled,
and shell approval under user control. It is not a security sandbox. OpenCode
owns the agent loop; keep step/output defaults conservative. Preserve transient
startup URL/timeout/reset/malformed JSON retries. Never claim agent readiness
without load → health → generation → OpenCode → real tool → real edit → post-edit
test → green PASS. Document exact boundaries of incomplete validation.

Prefer syntax checks, unit tests and tiny smoke projects. No broad benchmarks
without a concrete question. Preserve Git history and LICENSE. Never commit
GGUF, caches, node_modules, downloaded binaries or auth files.
