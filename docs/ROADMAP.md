# Incremental roadmap

Each phase ends in evidence and architectural review. Nothing below is authorization to
implement a later phase during Phase 1. Phase numbers after Phase 2 are provisional.

| Phase | Small deliverable | Exit evidence |
| --- | --- | --- |
| 1 — foundation (current) | V1 audit, hardware study, stack decision, modular skeleton, strict minimal manifest, CLI and tests | Tests/lint/package smoke; reviewer accepts boundaries and unresolved risks |
| 2 — minimal software drawing feasibility | Primitive-only backend adapter and bounded single-frame surface lifecycle; static diagnostic fixtures | Inspected curves/alpha/clips, repeated-frame memory, 360p/720p measurements, deterministic hashes; no rigs/world/audio/video |
| 3 — code-authored catalog foundations | One reusable character definition/rig and one small environment recipe, approved IDs and parameter limits | Identity/geometry contracts and static compositions; independent review before animation |
| 4 — deterministic animation | Frame-index evaluation, one articulated action, camera/depth basics | Timing/pose invariants, out-of-order frame equivalence and movement review |
| 5 — scene composition/style | Reusable environment system, bounded lights/effects, shot templates and typography | Consistent look, mobile readability and measured scene memory |
| 6 — media/timing | Bounded FFmpeg process adapter, supplied audio/timestamp contracts and synchronization | Failure/cleanup tests, process-tree budget, frame/audio timing evidence |
| 7 — production orchestration/review | Preview workflow, technical output checks, selected visual checks and explicit artistic review | Original short reel compared with reference dimensions; no automatic art-quality guarantee |

## Suggested Phase 2 assignment

Start only after Phase 1 review. Confirm the chosen software backend on Ubuntu before building
expensive systems around it. Install one candidate binding in a separate measured development
environment; pin native versions and record setup. Define a narrow drawing/surface ownership
protocol based on actual primitive needs. Implement lines, filled paths, basic transforms,
clip and alpha only. Produce a static diagnostic image from trusted code, not agent-defined
arbitrary drawing instructions. Test native buffer layout, bounded cleanup and repeated draws.

Measure 360×640 and 720×1280 against the proposed memory envelopes. Record environment and
methodology. Compare one alternative only if Cairo fails a specific acceptance criterion.
Keep dependency/contract/CLI changes small. Add a drawing command only if its meaning and
limitations can be truthfully advertised. Do not promote the foundation manifest to
`render_ready: true`: characters, timing and scene compilation still will not exist.

Phase 2 acceptance requires edge/alpha visual review, same-environment pixel reproducibility,
no growing surface/cache retention, measured memory with headroom, and a documented backend
accept/reject decision. Throughput is measured, not assumed. Encoder feasibility remains an
explicit later gate unless the architect separately authorizes a minimal encoding experiment.

## Phase 1 review questions

- Is Cairo the right first experiment, with Skia or Pillow retained as alternatives?
- Is a 256 MiB experimental process-tree envelope realistic for the deployment worker?
- Is the minimal non-renderable manifest appropriately narrow, with later scene language versioned?
- Should fps/profile scope change before stabilization? Are frame timing and error contracts clear?
- Which text shaping/font and redistribution licenses should later phases adopt?

Review outcome should explicitly accept, revise or reject decisions. Stop here until that review.
