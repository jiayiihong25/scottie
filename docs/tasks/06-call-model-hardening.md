# 06 — Harden call_model: empty completions, retries, timeout

**Size:** S · **Status:** done — empty completions raise; retries/timeout come from
the OpenAI SDK client config (4 retries, 120s per attempt) rather than a custom
loop; stray `pacing_agent` alias removed.

## Problem

Three gaps in the one function every agent node depends on.

**1. `call_model` can return `None`.**
`graph/models.py:71` returns `response.choices[0].message.content`, which is
`None` on a refusal or an empty completion. `graph/nodes/concept_agent.py:37`
then calls `.strip()` on it and dies with a bare `AttributeError` and no
indication of which alias or task type produced it. For a 6am unattended
run, that's a useless traceback.

`card_agent._parse_card` (`graph/nodes/card_agent.py:62-63`) already handles
this correctly — copy that pattern.

**2. No retries.** `docs/orchestration-design.md` names retry handling as one
of the reasons the wrapper exists, but there is none. The config routes to
free-tier providers first, which are exactly the providers most likely to
rate-limit or drop a request. A single flaky call kills the morning packet.

**3. No timeout.** A hung request hangs the Routine indefinitely with no
output and no error.

## What done looks like

- Raise an explicit error naming the task type and alias on an empty
  completion, instead of returning `None` into a node that will misuse it.
- Bounded retry with backoff on transient failures (timeouts, 429s, 5xx).
  **Not** on a 4xx that will fail identically every time — retrying an auth
  error three times just delays the inevitable.
- An explicit timeout per request.
- Retries stay invisible to nodes; exhausting them raises, per the
  fail-loudly rule. The wrapper's contract is "returns a usable string or
  raises" — nodes should never have to defend against it.

## Also worth doing here

`config/models.yaml:8` defines a `pacing_agent: auto/cheap` alias for a node
that makes no model calls at all — `pacing_agent` is deliberately
LLM-free and verified to contain zero `call_model` usage. The stray alias is
harmless but implies the opposite of the design. Delete it.

## Files

- `graph/models.py:44-71`
- `graph/nodes/concept_agent.py:37`
- `graph/nodes/card_agent.py:62-63` — the pattern to copy
- `config/models.yaml:8`
