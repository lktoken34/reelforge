"""Deterministic prompt -> validated production manifest planner (no AI, no network).

A small, explicit, rule-based planner for the supported MVP vocabulary. It reads a natural-
language prompt, extracts supported signals (environment, structure, actions, mood, focal
object), selects compatible shot presets from ``storylib`` and emits a ``production-0.1`` manifest
(2..20 ninety-frame segments). It never invents engine capability: unsupported requests raise a
clear error listing what is supported. An external LLM may produce the same manifest shape, but is
not required.

The planner chooses a *beat line* (an ordered list of (preset, mood, title, description) with a
target environment per beat), then expands it to the requested duration by lengthening traversal
or holding/establishing acts, so 15s (5 segments) and 60s (20 segments) share one structure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .storylib import ENVIRONMENTS, SHOT_PRESETS, VARIANT_COUNT, build_shot

SUPPORTED_DURATIONS = {15: 5, 60: 20}  # seconds -> 90-frame segments

# Keyword vocabulary. Each maps a regex to a tag; unknown words are ignored, but a prompt that
# matches no environment or no beat keyword is reported rather than silently defaulted.
ENV_KEYWORDS = {
    "frost_peak": r"snow|mountain|frost|peak|ridge|blizzard|ice|cold|alpine|glacier",
    "orchard": r"orchard|tree|grove|valley|farm|field|dusk|meadow|woodland",
}
ACTION_KEYWORDS = {
    "beacon": r"beacon|signal|emergency|distress|transmitter|radio|device|flare",
    "discover": r"discover|find|spot|notice|unusual|strange|mysterious|sees?",
    "investigate": r"investigate|examine|activate|press|inspect|study|switch",
    "run": r"run|flee|escape|rush|sprint|dash|bolt|safety",
    "storm": r"storm|wind|blizzard|weather|intensif",
    "rescue": r"rescue|answer|help|hope|saved|respond|reply",
    "lost": r"lost|alone|lonely|stranded|wander|trek|journey|cross",
}
MOOD_KEYWORDS = {
    "storm": r"storm|danger|threat|intense|fear|scared",
    "hopeful": r"hope|rescue|relief|safe|help|answer",
    "tense": r"strange|unusual|mysterious|suspense|worried|concern",
}


@dataclass(frozen=True)
class Beat:
    preset: str
    env: str
    mood: str
    title: str
    description: str
    variant: int = 0


@dataclass
class StoryPlan:
    prompt: str
    title: str
    environments: list[str]
    beats: list[Beat] = field(default_factory=list)
    duration_seconds: int = 60
    notes: list[str] = field(default_factory=list)


class PlanError(ValueError):
    """The prompt or duration cannot be served by the supported MVP vocabulary."""


def _tokens(prompt: str) -> str:
    return prompt.lower()


def _match(text: str, table: dict) -> list[str]:
    return [tag for tag, pattern in table.items() if re.search(pattern, text)]


def analyse(prompt: str) -> dict:
    """Extract supported signals from the prompt (pure, deterministic)."""
    if not isinstance(prompt, str) or not prompt.strip():
        raise PlanError("Provide a non-empty story prompt")
    text = _tokens(prompt)
    envs = _match(text, ENV_KEYWORDS)
    actions = set(_match(text, ACTION_KEYWORDS))
    moods = _match(text, MOOD_KEYWORDS)
    if not envs:
        raise PlanError(
            "No supported location recognised. Supported environments: "
            + ", ".join(f"{k} ({ENVIRONMENTS[k]['display']})" for k in ENVIRONMENTS)
            + ". Mention snow/mountain or orchard/valley."
        )
    return {"environments": envs, "actions": actions, "moods": moods, "text": text}


# A beat carries its act so expansion can grow each act independently and keep the arc coherent.
# Acts: 1 discovery, 2 storm/decision, 3 journey, 4 resolution.
def _beatline(signals: dict) -> list[tuple[str, str, str, int]]:
    """Return an ordered list of (preset, env, mood, act) describing the core story.

    Beats are chosen only from what the prompt supports. A beacon set piece is included only when
    the prompt mentions a signal/emergency and the Frost Peak beacon environment is available.
    """
    envs = signals["environments"]
    actions = signals["actions"]
    primary = envs[0]
    secondary = envs[1] if len(envs) > 1 else None
    beacon_ok = "beacon" in actions and (primary == "frost_peak" or secondary == "frost_peak")
    beacon_env = "frost_peak"
    line: list[tuple[str, str, str, int]] = []

    # Act 1 - discovery in the primary location.
    line.append(("establish", primary, "calm", 1))
    if actions & {"discover", "beacon", "lost"}:
        line.append(("reaction", primary, "tense", 1))
    if beacon_ok and ("investigate" in actions or "beacon" in actions):
        line.append(("investigate", beacon_env, "tense", 1))
        # Act 2 - the beacon answers; storm and a decision.
        line.append(("threat", beacon_env, "storm", 2))
        line.append(("resolve" if False else "reaction", beacon_env, "storm", 2))
    elif "discover" in actions:
        line.append(("reaction", primary, "storm", 2))

    # Act 3 - the journey: run to safety, or travel toward the secondary environment.
    if "run" in actions:
        line.append(("travel_run", secondary or primary, "storm", 3))
    elif secondary and secondary != primary:
        line.append(("travel", secondary, "hopeful", 3))
    else:
        line.append(("travel", primary, "hopeful", 3))

    # Act 4 - resolution in the final location.
    final_env = secondary if (secondary and secondary != primary) else primary
    if "rescue" in actions or beacon_ok:
        line.append(("resolve", final_env, "hopeful", 4))
    else:
        line.append(("reaction", final_env, "hopeful", 4))
    return line


# Titles/descriptions per preset, kept generic so any beat line reads as a story.
_BEAT_TEXT = {
    "establish": ("Arrival", "{who} arrives and takes in the {place}."),
    "reaction": ("Something is wrong", "{who} notices something and reacts."),
    "investigate": ("The beacon", "{who} reaches the emergency beacon and activates it."),
    "threat": ("The answer", "The beacon flares; the weather turns and {who} is startled."),
    "travel": ("The journey", "{who} travels on toward the {place}."),
    "travel_run": ("Run", "{who} breaks into a run across the {place}."),
    "resolve": ("Resolution", "{who} reaches safety and sees the signal answered."),
}


def plan_story(prompt: str, duration_seconds: int = 60, *, title: str | None = None) -> StoryPlan:
    if duration_seconds not in SUPPORTED_DURATIONS:
        raise PlanError(
            f"Unsupported duration {duration_seconds}s; choose one of "
            f"{sorted(SUPPORTED_DURATIONS)} seconds"
        )
    signals = analyse(prompt)
    line = _beatline(signals)
    segments_needed = SUPPORTED_DURATIONS[duration_seconds]

    # Expand to the exact segment count while keeping a coherent act arc: extra time is shared
    # across acts (lengthening each act's observation/travel), never ping-ponging locations.
    expanded = _expand(line, segments_needed)

    who = "Yellow Mellow"
    beats = []
    # Assign a distinct staging variant to each repeated (preset, environment) so the same preset
    # used more than once is staged differently (cycling within the preset's available variants).
    occurrence: dict[tuple[str, str], int] = {}
    for i, (preset, env, mood, _act) in enumerate(expanded):
        label, desc = _BEAT_TEXT[preset]
        place = ENVIRONMENTS[env]["display"]
        n = occurrence.get((preset, env), 0)
        occurrence[(preset, env)] = n + 1
        variant = n % VARIANT_COUNT.get(preset, 1)
        beats.append(
            Beat(
                preset,
                env,
                mood,
                f"{i + 1:02d} {label}",
                desc.format(who=who, place=place),
                variant,
            )
        )
    resolved_title = title or _title_for(signals, prompt)
    return StoryPlan(
        prompt=prompt,
        title=resolved_title,
        environments=signals["environments"],
        beats=beats,
        duration_seconds=duration_seconds,
        notes=[f"actions={sorted(signals['actions'])}", f"moods={signals['moods']}"],
    )


BeatT = tuple  # (preset, env, mood, act)

# Continuation menus per act: ordered presets used to lengthen an act into extra segments without
# repeating a set piece or an identical staged shot. Each act keeps a single environment.
_ACT_FILL = {
    1: [("travel", "calm"), ("reaction", "tense"), ("establish", "calm")],
    2: [("reaction", "storm"), ("reaction", "tense"), ("travel", "determined")],
    3: [
        ("travel", "determined"),
        ("reaction", "tense"),
        ("travel", "hopeful"),
        ("establish", "calm"),
    ],
    4: [("travel", "hopeful"), ("reaction", "warm"), ("establish", "warm")],
}


def _expand(line: list[BeatT], target: int) -> list[BeatT]:
    """Grow/shrink to ``target`` beats with a coherent, non-repeating act arc.

    Shrinking keeps the first ``target`` skeleton beats (establish first, the skeleton's final
    beat last). Growth allocates the extra beats across acts proportionally and fills each act from
    its continuation menu (distinct travel/observation angles in that act's environment). Set
    pieces (investigate, threat, resolve) are kept once and in order; the resolve stays last.
    """
    if target <= len(line):
        trimmed = list(line[:target])
        p, e, m, a = trimmed[0]
        if p != "establish":
            trimmed[0] = ("establish", e, "calm", a)
        trimmed[-1] = line[-1]
        return trimmed

    acts = sorted({b[3] for b in line})
    extra = target - len(line)
    # Distribute extra beats across acts round-robin (acts appear once each per pass).
    alloc = {act: 0 for act in acts}
    for k in range(extra):
        alloc[acts[k % len(acts)]] += 1

    last_act = acts[-1]
    out: list[BeatT] = []
    for act in acts:
        act_beats = [b for b in line if b[3] == act]
        env = act_beats[0][1]
        menu = _ACT_FILL.get(act, [("travel", "hopeful")])
        fills = [
            (menu[i % len(menu)][0], env, menu[i % len(menu)][1], act) for i in range(alloc[act])
        ]
        if act == last_act:
            # Keep the final set piece (the resolve) as the closing segment of the whole reel.
            out += act_beats[:-1] + fills + [act_beats[-1]]
        elif len(act_beats) == 1:
            # A single-beat act (e.g. a lone journey beat): continuation follows it.
            out += [act_beats[0]] + fills
        else:
            # Lengthen mid-act so the closing set piece (threat) stays at the act's end.
            out += [act_beats[0]] + fills + act_beats[1:]
    return out


def _title_for(signals: dict, prompt: str) -> str:
    if "frost_peak" in signals["environments"] and "beacon" in signals["actions"]:
        return "Yellow Mellow - The Signal Across the Valley"
    if "orchard" in signals["environments"]:
        return "Yellow Mellow - The Orchard Discovery"
    return "Yellow Mellow - " + prompt.strip()[:60]


def build_production_manifest(plan: StoryPlan) -> dict:
    """Realise a StoryPlan as a validated-shape production-0.1 manifest (not yet compiled)."""
    segments = []
    for i, b in enumerate(plan.beats):
        sb = build_shot(
            b.preset,
            b.env,
            title=b.title[:120],
            description=b.description[:800],
            mood=b.mood,
            variant=b.variant,
        )
        segments.append({"id": f"seg_{i + 1:02d}", "storyboard": sb})
    return {
        "schema_version": "production-0.1",
        "title": plan.title[:120],
        "segments": segments,
        "audio": None,
    }


def plan_summary(plan: StoryPlan) -> dict:
    """A compact, human/agent-readable description of the plan and its beats."""
    return {
        "prompt": plan.prompt,
        "title": plan.title,
        "duration_seconds": plan.duration_seconds,
        "segments": len(plan.beats),
        "environments": plan.environments,
        "notes": plan.notes,
        "beats": [
            {
                "index": i + 1,
                "preset": b.preset,
                "environment": b.env,
                "mood": b.mood,
                "variant": b.variant,
                "title": b.title,
                "description": b.description,
            }
            for i, b in enumerate(plan.beats)
        ],
    }


def supported() -> dict:
    return {
        "durations_seconds": sorted(SUPPORTED_DURATIONS),
        "environments": {k: v["display"] for k, v in ENVIRONMENTS.items()},
        "shot_presets": sorted(SHOT_PRESETS),
        "beat_keywords": sorted(ACTION_KEYWORDS),
        "character": "yellow_mellow_v2",
    }
