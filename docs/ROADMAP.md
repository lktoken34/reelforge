# Incremental roadmap

Phase 1 is approved with changes. Phase 2A was approved at c70d2f2. Phase 2B was approved at 7133f244. Phase 2C implementation was approved; target validation was blocked before rendering. Phase 2C.1 memory compatibility awaits target evidence and review.
No next-milestone implementation is authorized by this document.

Each phase ends in evidence and architectural review. Nothing below is authorization to
implement a later phase during Phase 1. Phase numbers after Phase 2 are provisional.

| Phase | Small deliverable | Exit evidence |
| --- | --- | --- |
| 1 — foundation (complete) | V1 audit, hardware study, stack decision, modular skeleton, strict minimal manifest, CLI and tests | Tests/lint/package smoke; reviewer accepts boundaries and unresolved risks |
| 2A — minimal software drawing feasibility (approved) | Primitive-only backend adapter and bounded single-frame surface lifecycle; static diagnostic fixtures | Inspected curves/alpha/clips, repeated-frame memory, 360p/720p measurements, deterministic hashes; no rigs/world/audio/video |
| 2B — bounded CPU video (approved) | Cairo-to-FFmpeg raw pipe, fixed motion fixture, verification and process-tree evidence | Silent 5s MP4s, failure tests, decoded-repeat comparison and review |
| 2C — cloud deployment gate (current) | Prebuilt installation, sequential short/long validation, resource/recovery evidence | Actual target-VM results and external architectural approval; development host is supplementary |
| 2C.1 — VM memory compatibility (current) | Read-only topology discovery and explicitly authorized guest procfs policy | Strict/fixture regressions, new wheelhouse, actual VM re-test and external review |
| 3 — code-authored catalog foundations | One reusable character definition/rig and one small environment recipe, approved IDs and parameter limits | Identity/geometry contracts and static compositions; independent review before animation |
| 4 — deterministic animation | Frame-index evaluation, one articulated action, camera/depth basics | Timing/pose invariants, out-of-order frame equivalence and movement review |
| 5 — scene composition/style | Reusable environment system, bounded lights/effects, shot templates and typography | Consistent look, mobile readability and measured scene memory |
| 6 — media/timing | Bounded FFmpeg process adapter, supplied audio/timestamp contracts and synchronization | Failure/cleanup tests, process-tree budget, frame/audio timing evidence |
| 7 — production orchestration/review | Preview workflow, technical output checks, selected visual checks and explicit artistic review | Original short reel compared with reference dimensions; no automatic art-quality guarantee |

## Phase 2A assignment (implemented; see report)

Phase 1 review authorized this milestone. Confirm the chosen software backend on Ubuntu before building
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

Review outcome should explicitly accept, revise or reject decisions. Stop after Phase 2C.1 for external review. Do not begin catalog foundations before the deployment gate is accepted.
