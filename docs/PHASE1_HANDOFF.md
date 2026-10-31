# Phase 1 architectural review handoff (historical)

## 1. Architecture and rationale

The implemented foundation is Python 3.12, JSON Schema Draft 2020-12, a packaged local CLI,
JSON diagnostics and a locked dependency graph. Recommend replaceable Cairo/Pycairo CPU
rasterization and bounded FFmpeg encoding later. This matches code-authored vector cutout
storytelling while allowing explicit control over memory and keeping weak agents in JSON.
Native backend/encoder components have not been implemented or installed as runtime requirements.
See ARCHITECTURE.md, HARDWARE_CONSTRAINTS.md and ADR 0001 for alternatives and tradeoffs.

## 2. V1 reuse/rewrite

Reuse ideas: declarative shots, validate-first workflow, logical coordinates, pure timing
functions, streaming frames, consistent identity and separate technical/artistic review.
Rewrite contracts, backend boundaries, cache/process lifecycle, timing, fonts and QA. Do not
port placeholder art or rely on external PNG packs. No V1 runtime code was copied.

## 3. Files

All files in FILE_MANIFEST.md are new. Original attachments remain unchanged. The repository
contains the six requested documents, additional agent-contract/convention/decision/verification
notes, a foundation example, package/schema/CLI code, future-module boundary notes, uv setup
and lock, CI configuration and smoke tests. Excluded: virtual environments, caches, reference
media, V1 source, build outputs and generated videos.

## 4. Actual checks

42 V2 tests pass; Ruff lint and format checks pass; frozen sync and lock consistency pass;
wheel/sdist build succeeds; clean installed-wheel commands work outside source checkout.
V1's five baseline tests pass, with validation weaknesses confirmed separately. Detailed
commands/results and scope limits are in VERIFICATION.md. Remote CI was not run.

## 5. Risks still open

No constrained-host visual/encoded-job feasibility evidence yet. Cairo buffer/color conversion,
font shaping and licenses, native build pinning, encoder memory, runtime resource enforcement,
future catalog complexity and cross-platform pixel/video determinism remain unresolved. The
256 MiB process-tree envelope is an experimental target, not a verified guarantee. A manifest
validation pass says nothing about art quality or render readiness. Future narrative coverage
will depend on the richness of trusted code-authored catalogs and action templates.

## 6. Suggested Phase 2

After review, build a primitive-only software backend experiment with explicit surface ownership.
Check curves, transforms, clipping and alpha; measure repeated-frame memory and deterministic
pixels at 360p/720p on the actual Ubuntu worker. Compare an alternative if Cairo fails a
specific gate. No rigs, environments, full animation, lighting/audio or production pipeline.

**Phase 1 is complete. Work stops for external architectural review.**
