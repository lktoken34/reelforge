# Phase 1 verification record (historical)

Date: 2026-10-31. Actual execution host: Ubuntu 24.04.3 LTS, Linux x86_64,
CPython 3.12.14, uv 0.13.4. This host was not constrained to 4 vCPUs/0.4 GiB for these checks.

| Check actually performed | Final result |
| --- | --- |
| Uploaded V1 unittest suite | 5 passed; includes existing small-frame smoke test |
| V1 focused invalid-input probes | Unknown property, NaN duration and square output accepted; malformed nested scene raised AttributeError; documented in audit |
| V2 `uv sync --frozen` | Passed; packaged editable installation works |
| V2 `uv lock --check` | Passed; 19 resolved packages in full cross-platform graph |
| V2 `uv run --frozen pytest` | **42 passed in 1.33s** |
| Ruff check | Passed |
| Ruff format check | 9 Python files already formatted |
| `python -m build --no-isolation` | Wheel and source archive built; wheel built from sdist |
| Clean wheel environment | Installed hash-locked runtime dependencies and wheel with no development dependencies |
| Installed console CLI from `/tmp` | capabilities, schema, validate all passed with parseable JSON and empty stderr |
| Installed module entrypoint from `/tmp` | `python -m reelforge capabilities` passed; imported module confirmed inside wheel environment |
| Reference metadata | ffprobe reported 720×1280, 30 fps, H.264/AAC, 87.074830s |
| Reference visual spot check | Inspected a downscaled frame at 10s; no full motion/audio review |

Test coverage includes schema self-validation and bundled example consistency, missing and
unknown fields, unsupported version/profile/fps, wrong types including boolean durations,
invalid IDs including trailing newline, duplicate scenes, per-scene/total duration bounds,
blank/oversized intent, input nonmutation, stable/sensitive hashes, UTF-8 errors, duplicate
JSON keys, NaN/Infinity, byte/nesting bounds, bounded diagnostics, quoted-bracket handling,
CLI capability honesty, reproducible validation, usage errors, missing files and help behavior.

The nesting check is an explicit 32-container guard independent of Python recursion settings.
Deep malformed input does not depend on a particular interpreter/test-runner recursion limit.

A single installed-wheel validation process peaked at **19736 KiB (~19.3 MiB) RSS**,
measured with Linux `resource.getrusage(RUSAGE_CHILDREN).ru_maxrss` in an otherwise clean
launcher. This is one tiny-manifest observation, not a runtime memory ceiling or rendering
benchmark. The interpreter and schema imports are included; no rendering/encoder is involved.

## Not performed / not established

GitHub-hosted CI was configured, not executed remotely. No Cairo, Skia, Pillow comparison,
encoded-job performance test, constrained cgroup trial, target-host deployment, audio sync,
production render, character/world implementation or advanced visual QA was performed for V2.
The V1 image smoke is not a V2 rendering implementation. No claim of reference quality or
rendering feasibility follows from the foundation tests. Native/system reproducibility remains
unverified. `/usr/bin/time` was unavailable in this host; no GNU time result is claimed.

For the current Phase 2A results, see PHASE2A_REPORT.md. This file preserves the original
foundation evidence and does not describe the newer optional backend tests.
