# Phase 1 architecture

Status: foundation implemented; all visual/media modules are planned. The external AI
architect/reviewer should review this proposal before any Phase 2 implementation.

## Boundaries and ownership

The authoring agent chooses from published capabilities and writes declarative JSON. A
trusted engine validates, resolves approved catalog IDs, compiles an immutable scene plan,
evaluates it at an integer frame index, draws bounded surfaces and streams frames to an
encoder. An operator reviews artistic quality. This separates creative decisions from
resource management and implementation details a weaker agent should not control.

| Module | Responsibility | Dependency rule | Phase 1 status |
| --- | --- | --- | --- |
| `core` | Diagnostic values; future time/value types | Standard library only | Issue/InputError implemented |
| `contracts` | Versioned JSON, loading, structural/semantic validation | core + jsonschema; no render imports | Implemented minimal draft |
| `cli` | Discover features, emit schema, validate files | contracts/core; no system processes | Implemented |
| `catalog` | Versioned code recipes for character/environment/prop identities | core; no CLI/media | Documentation only |
| `planning` | Resolve IDs, validate references, compile immutable intermediate representation | core/contracts/catalog; no raster backend | Documentation only |
| `animation` | Evaluate approved action templates at exact frame indices | core/compiled plan; no filesystem | Documentation only |
| `rendering` | Draw evaluated vector commands into owned software surfaces | core; backend behind adapter | Documentation only |
| `resources` | Preflight budgets, byte-bounded caches, buffer lifetime accounting | core; no story logic | Documentation only |
| `media` | Bounded encoder pipe, process lifecycle, later supplied audio | core; consumes frames, no catalogs | Documentation only |
| `quality` | Later technical checks and review artifacts | core + media metadata; never approves art automatically | Documentation only |

Dependencies point from orchestration to independent components. Catalog declarations must
not reach into media; validation must not load native rendering libraries. Avoid a generic
plugin system and arbitrary agent-provided code. In Phase 1 the CLI calls contracts directly;
add orchestration only when there are actual operations to coordinate.

## Implemented contract versus eventual scene language

`2.0-draft1` is intentionally a small foundation manifest: IDs, explicit seed, output profile,
fps, ordered scenes, duration in frames and descriptive intent. It is not an executable scene
specification. Strict unknown-field rejection prevents invented future capabilities. The
schema is packaged once under contracts; `reelforge schema` exposes the same source of truth.
Semantic validation additionally checks unique scene IDs and a total frame limit.

Future drafts should introduce typed catalog references and constrained actions only after
those features exist. The eventual agent interface should resemble catalog discovery →
manifest validation → plan inspection → preview → reviewed render. Proposed operations
`catalog`, `plan`, `preview`, `render` and `inspect` are **not implemented commands**. Their
names are proposals, not promises. Do not add empty implementations to advertise progress.

A future visual scene will reference a versioned character/environment recipe and an approved
shot/action template with bounded parameters. It will not embed arbitrary drawing code,
shader source, Python imports or free-form instructions interpreted at render time. Scripts,
audio and timestamps will be converted by the authoring agent into explicit supported fields;
the renderer itself will never call a model. A separate trusted engineering workflow extends
the catalog when new story elements are needed. This is the key limit on arbitrary script
coverage by weaker agents.

## Proposed backend and frame boundary (not implemented)

Prefer Cairo image surfaces via Pycairo: CPU vector curves, strokes, transforms, clipping and
alpha composition suit code-authored cutout art. Backend-native objects must stay inside the
adapter. A later backend protocol should take an evaluated draw-list and an owned target
surface, and release all temporary surfaces before returning. Typed commands should cover
only the needed primitives; do not mirror an entire graphics API in JSON.

Future frame metadata must specify width, height, stride, byte order, alpha convention,
color space and owner/lifetime. Cairo ARGB32 is native-endian premultiplied alpha. It cannot
be treated blindly as packed RGB24. Flatten onto an opaque background and explicitly convert
or describe the encoder input format; check stride/padding. Budget any conversion copy.
Use a fixed sRGB-like output convention initially, document compositing behavior, and review
color/alpha goldens before claiming backend parity. Wide-gamut/linear-light grading is deferred.

Proposed media boundary: consume one frame at a time through a bounded pipe with backpressure.
No frame list or unlimited queue. Future FFmpeg invocation uses an argument list, one codec
thread initially, explicit filter-thread settings, bounded diagnostics, timeout/cancellation,
cleanup, and temporary output + atomic rename after success. No partial output should look
final. Encoder failure must propagate a stable domain error, not an opaque BrokenPipeError.
No subprocess or encoder is present in this phase.

## Determinism policy

Implemented: deterministic validation, no inferred defaults, strict JSON loader, stable
canonical manifest digest for the same values/numeric forms regardless of object-key order.
No clock, randomness or network is used by validation. Hashing does not normalize Unicode or
numeric forms such as `30` versus `30.0`; this is an input identity, not a semantic scene hash.

Future: integer global frame indices, half-open scene intervals `[start, end)`, exact rational
time `frame/fps`, deterministic draw order (depth then stable ID), and per-entity random streams
derived using SHA-256 of versioned stable IDs and the explicit project seed. Re-evaluating a
frame out of order must not alter it. Avoid accumulated float delta-time and mutable RNG state.

Target exact pixel hashes within a pinned OS/library/font/CPU configuration. Cross-backend
pixel identity is not promised; antialiasing, fonts and native math differ. Byte-identical MP4
requires a separately pinned codec build, threading, flags and metadata policy; it is not
implied by deterministic pixels. Future job identities include engine/contract/catalog versions,
canonical manifest, font/source checksums, profile and backend/encoder fingerprints.

## Failure and evolution policy

Implemented user errors are bounded structured diagnostics with JSON Pointer paths and
stable code categories. Schema prose is diagnostic text and may change with dependency
versions; agents must use code/path rather than parsing English. No silent visual fallback.

Future validation stages: syntax → schema → references/capabilities → semantic constraints →
resource preflight. Invalid data never reaches rasterization. Preflight must reject a job
that cannot fit the selected budget; changing resolution/fps/quality requires an explicit
manifest change, never silent degradation. Invalid image/audio paths, huge buffers, missing
fonts and unavailable actions must fail before expensive work. No assets or external paths
are accepted in the current manifest.

## Open architectural decisions

Confirm Cairo versus Skia on the constrained host; decide text shaping/font packaging and
whether a Cairo/Pillow conversion dependency is needed. Approve future draw-command and
catalog contracts only after a minimal backend experiment. Choose redistribution license,
font licenses and native build pinning policy before shipping the engine outside the project.
