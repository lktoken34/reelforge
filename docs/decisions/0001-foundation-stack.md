# ADR 0001 — Small Python foundation, replaceable native CPU drawing

Status: proposed architecture; foundation implementation complete, pending external review.
Date: 2026-10-31.

## Context

A weaker AI driver needs discoverable data contracts rather than engine-writing instructions.
The eventual Ubuntu worker has 4 vCPUs, no GPU and 0.4–1.0 GiB available RAM. Code-authored
cutout animation needs consistent reusable geometry and explicit lifetime management.

## Decision

Use CPython 3.12, a packaged src-layout CLI and JSON Schema Draft 2020-12. jsonschema is the
only foundation runtime dependency. Use uv with a committed full lock and pinned development
/build tools. Do not introduce an LLM framework, web server, browser, GPU runtime or generic
plugin loader. A conventional local CLI is portable across agent vendors and easy to test.

Recommend Pycairo/Cairo image surfaces for later CPU vector rendering. Keep the draw-list and
owned-frame boundary independent of that backend. Recommend a bounded FFmpeg/libx264 pipe for
later encoding. Neither Cairo nor FFmpeg is a Phase 1 dependency or implemented adapter.

JSON Schema is selected over a handwritten validator alone for a machine-readable contract
agents/editors can discover. Semantic checks complement it. Pydantic is a viable alternative,
but introducing both would duplicate the source of truth and invite coercion/schema drift.
No dataclass hierarchy for hypothetical scene/rig objects is needed before those systems exist.

## Consequences

The Python lock does not pin system libraries or fonts. Exact render reproducibility will need
a separate native environment fingerprint, later possibly an image digest. Cairo buffer
conversion/text shaping need real experiments. Explicit limited catalogs constrain creative
coverage but reduce weak-agent errors. Runtime admission and budgets must be implemented later;
the present manifest bounds are not a rendering resource scheduler.

See HARDWARE_CONSTRAINTS.md for source links, arithmetic, alternatives and the measurement gate.
