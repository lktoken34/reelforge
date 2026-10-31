# Agent-facing foundation contract

The three implemented commands are `reelforge capabilities`, `reelforge schema` and
`reelforge validate PATH`. Console entrypoint and `python -m reelforge` are equivalent.
`schema` prints a raw JSON Schema; the other two commands print a single JSON object.
`--help` uses conventional text and exits 0. Usage/input errors use stdout JSON and exit 2;
input I/O failures exit 3. Unexpected programming faults are not disguised as input errors
and may produce a traceback/nonzero exit; capture stderr separately.

```json
{
  "schema_version": "2.0-draft1",
  "project_id": "my_reel",
  "seed": 7,
  "output": {"profile": "preview_360p", "fps": 30},
  "scenes": [
    {"id": "opening", "duration_frames": 90, "intent": "Establish the location."}
  ]
}
```

All shown fields are required. All objects reject unknown keys. No defaults, YAML, comments,
remote schemas, files, audio paths, expressions or executable extensions are supported.
IDs are exactly 1–64 lowercase ASCII letters/digits/underscores, beginning with a letter. Seed is an integer from 0 through 2147483647. JSON Schema
integer semantics accept mathematically integral values such as `30.0`; use integer literals
for predictable authoring. Booleans are not integers. Output profiles name 360×640 and
720×1280, respectively; supported integer fps values are 24, 25, 30. These are intent metadata,
not a promise that a future render will fit the host.

Scenes are in timeline order, 1–256 entries, with globally unique IDs. Duration is 1–1800
frames per scene, at most 18000 frames in total. These are conservative manifest guardrails,
not performance-derived production limits. At 30 fps, 90 frames means 3 seconds. There is no
implicit per-shot rounding. Future intervals will be contiguous and half-open. Intent is
1–2000 characters with at least one non-whitespace character. It is retained for humans;
Phase 1 never converts it to art or animation. Validation is structural, not creative.

Files must be UTF-8 JSON, at most 1048576 bytes. Duplicate keys, NaN/Infinity literals and numeric overflow such as `1e309` are
rejected before schema validation. Malformed JSON or nesting beyond 32 containers is reported as JSON_INVALID; this is a bounded
local-file tool, not a hardened server for hostile input. Do not pass FIFOs, devices or network
mounts as manifests. Error count is capped at 32; fix reported issues and revalidate to reveal
additional errors. Schema checks precede semantic checks. A path points to the failing value
or containing object for a missing/extra field. Root path is the empty string.

Successful validation includes:

```json
{"ok": true, "schema_version": "2.0-draft1", "manifest_sha256": "<64 hex digits>",
 "scene_count": 1, "total_frames": 90, "render_ready": false}
```

An unsupported property inside output produces a diagnostic of this shape:

```json
{"ok": false, "errors": [{"code": "SCHEMA_ADDITIONALPROPERTIES", "path": "/output",
 "message": "Additional properties are not allowed ('magic' was unexpected)"}]}
```

| Code | Repair |
| --- | --- |
| `CLI_USAGE` | Use one advertised command and its required arguments |
| `INPUT_IO` | Check the local file path and read permissions |
| `INPUT_TOO_LARGE` | Reduce manifest size below 1 MiB |
| `JSON_INVALID`, `JSON_DUPLICATE_KEY`, `JSON_NONFINITE` | Fix encoding/JSON syntax or forbidden duplicate/non-finite values |
| `SCHEMA_REQUIRED`, `SCHEMA_TYPE`, `SCHEMA_ENUM`, `SCHEMA_CONST` | Match required fields, types, capabilities and exact schema version |
| Other `SCHEMA_<KEYWORD>` codes | Repair the indicated schema constraint |
| `SCENE_ID_DUPLICATE` | Assign a distinct stable scene ID |
| `TIMELINE_LIMIT` | Reduce total scene duration to 18000 frames or less |

Weaker-agent repair procedure: preserve unrelated values, change the indicated field, retry
at most three times, then return unresolved diagnostics to the operator. Never edit schema
or engine code to force acceptance. Unavailable features require a trusted engineer and a
new reviewed capability, not invented JSON. No artistic quality score is emitted.

Future drafts will add catalog IDs, parameters, camera/action templates, captions and local
audio references when those systems exist. The same staged validation/diagnostics contract
should remain, but this draft must not be represented as a complete future scene language.

Phase 2A note: the optional trusted-Python drawing backend is deliberately absent from these
commands and this schema. Existing manifests are still not render-ready.
