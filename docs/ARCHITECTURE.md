# ReelForge V2 architecture

Status: Phase 1 foundation approved with changes. Phase 2A implements a minimal trusted-code
Cairo vector experiment; scene/rig/animation systems remain planned. External
Phase 2A is approved; Phase 2B adds a bounded diagnostic video path. Review is required before
the next milestone. See VIDEO_PIPELINE.md and PHASE2B_REPORT.md.

Phase 2C implementation is approved. Phase 2C.1 adds explicit engineering memory
observability policies without changing rendering or episode contracts; see
[MEMORY_OBSERVABILITY.md](MEMORY_OBSERVABILITY.md). Target deployment approval remains pending.

Phase 3A adds a `characters` boundary for one immutable skeleton, local artwork and pure
motion presets. It returns existing DrawPath values and imports no native graphics objects.
It is independent of episode planning and deployed-resource policy. See CHARACTER_RIG.md.

Phase 3A.1 refines this same rig via planar contact solving, a continuous cadence/contact
clock, bounded analytical secondary roles and additive acting presets. No native/media/resource
boundary changed. See CHARACTER_POLISH.md and PHASE3A1_REPORT.md for review status.

## Boundaries and ownership

The authoring agent chooses from published capabilities and writes declarative JSON. A
trusted engine validates, resolves approved catalog IDs, compiles an immutable scene plan,
evaluates it at an integer frame index, draws bounded surfaces and streams frames to an
encoder. An operator reviews artistic quality. This separates creative decisions from
resource management and implementation details a weaker agent should not control.

| Module | Responsibility | Dependency rule | Current status |
| --- | --- | --- | --- |
| `core` | Diagnostic values; future time/value types | Standard library only | Issue/InputError implemented |
| `contracts` | Versioned JSON, loading, structural/semantic validation | core + jsonschema; no render imports | Implemented minimal draft |
| `cli` | Discover features, emit schema, validate files | contracts/core; no system processes | Implemented |
| `characters` | One original cutout, generic rigid hierarchy and deterministic presets | core/rendering values; no native objects, media or episode dependencies | Phase 3A experimental implementation |
| `catalog` | Versioned code recipes for character/environment/prop identities | core; no CLI/media | Documentation only |
| `planning` | Resolve IDs, validate references, compile immutable intermediate representation | core/contracts/catalog; no raster backend | Documentation only |
| `animation` | Evaluate approved action templates at exact frame indices | core/compiled plan; no filesystem | Documentation only |
| `rendering` | Draw trusted vector commands into owned software surfaces | standalone value/protocol boundary; optional native adapter | Primitive-only Cairo experiment implemented |
| `resources` | Memory preflight and sampled process-tree accounting; future caches | core; no story logic/media dependency | Conservative Linux diagnostic policy implemented |
| `media` | Bounded encoder pipe, process lifecycle and verification; audio deferred | core + Surface protocol; no Cairo/catalog imports | Phase 2B engineering path implemented |
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

## Primitive backend and future frame/media boundary

The Phase 2A experiment uses Cairo image surfaces via Pycairo: CPU vector curves, strokes, transforms, clipping and
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

Media boundary: consume one frame at a time through a bounded pipe with backpressure.
No frame list or unlimited queue. Future FFmpeg invocation uses an argument list, one codec
thread initially, explicit filter-thread settings, bounded diagnostics, timeout/cancellation,
cleanup, and temporary output + atomic rename after success. No partial output should look
final. Encoder failure must propagate a stable domain error, not an opaque BrokenPipeError.
This boundary is implemented narrowly in Phase 2B; no episode compiler or audio exists.

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

Cairo passed the primitive experiment on the available larger host; still confirm it on the constrained target host; decide text shaping/font packaging and
whether a Cairo/Pillow conversion dependency is needed. Approve future draw-command and
catalog contracts only after a minimal backend experiment. Choose redistribution license,
font licenses and native build pinning policy before shipping the engine outside the project.

## Phase 2A implementation delta

The implemented Renderer/Surface protocols, immutable path/paint/transform values and Cairo
adapter are documented in CAIRO_BACKEND.md. Native objects and short-lived memoryviews remain
inside that adapter. Explicit target byte accounting is implemented; whole-job resource
preflight is still planned. Linear gradients and per-path source-over alpha are supported.
The agent contract/schema/CLI remain unchanged except that JSON numeric overflow is rejected
consistently before validation. Foundation `render_ready` remains false.

## Phase 2B implementation delta

The Surface protocol adds opaque BGRA fd transfer without exposing native buffers. The media
module validates layout/count, owns FFmpeg and publishes only a completed encode. Core pipe
utilities handle finite waits and borrowed views. Resources owns Linux admission/measurement
without importing media. The fixed diagnostic frame function is not a general animation engine.
See VIDEO_PIPELINE.md for exact contracts and PHASE2B_HARDWARE.md for measured whole-job scope.

## Phase 3B environment boundary

`environments` now owns one pure vector orchard recipe, explicit immutable depth layers,
bounded camera math and a native-free six-field preset. It returns the existing DrawPath
vocabulary. No episode schema, backend, encoder or resource-policy boundary changed.
See CINEMATIC_ENVIRONMENT.md and PHASE3B_REPORT.md; external review is pending.
