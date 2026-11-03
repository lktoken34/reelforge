"""Numerical motion-quality checks for a sampled Yellow Mellow V2 performance.

All measurements are in character units (1 unit = stage scale logical px; 2.3 logical =
4.6 output px in the 720x1280 showcase). They complement, and do not replace, inspection of
rendered frames.
"""

from __future__ import annotations

import math
import statistics

from .rig import NECK_LEN, SHIN, SIDE_OUT, THIGH, pivot_local

GROUND_EPS = 0.15
SLIDE_TOLERANCE = 0.05
PENETRATION_TOLERANCE = 0.05


def _corr(a, b):
    if len(a) < 3:
        return 0.0
    ma, mb = statistics.fmean(a), statistics.fmean(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va < 1e-12 or vb < 1e-12:
        return 1.0 if va < 1e-12 and vb < 1e-12 else 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b, strict=True)) / math.sqrt(va * vb)


def _swap(name: str) -> str:
    if name.startswith("near_"):
        return "far_" + name[5:]
    if name.startswith("far_"):
        return "near_" + name[4:]
    return name


def _contact_x(cf, side):
    """World x of the foot's ground reference: ankle ref when flat, roll pivot otherwise."""
    s = cf.state
    foot = s.pose.foot(side)
    if abs(foot.pitch) < 1e-9:
        return foot.x
    px, _ = pivot_local(foot.pitch, s.f)
    return foot.x + s.sign * px


def _points(cf):
    s = cf.state
    pts = {}
    for name, j in s.joints.items():
        pts[name] = s.world((j.x, j.y))
    for side in ("near", "far"):
        leg = s.legs[side]
        pts[f"{side}_hip"] = s.world(leg.hip)
        pts[f"{side}_knee"] = s.world(leg.knee)
        pts[f"{side}_ankle"] = s.world(leg.ankle)
    return pts


def analyse(perf, *, sections=()) -> dict:
    frames = perf.frames
    samples = [perf.sample(f) for f in range(frames)]
    pts = [_points(cf) for cf in samples]
    soles = []
    for cf in samples:
        s = cf.state
        row = {}
        for side in ("near", "far"):
            heel, toe = s.sole_points(side)
            row[side] = (s.world(heel), s.world(toe))
        soles.append(row)

    max_slide = 0.0
    slide_events = []
    max_pen = 0.0
    landings = {"near": [], "far": []}
    airborne = []
    for f in range(frames):
        lows = []
        for side in ("near", "far"):
            heel, toe = soles[f][side]
            max_pen = max(max_pen, heel[1], toe[1])
            lows.append(max(heel[1], toe[1]))
            if f > 0:
                prev_side = (
                    side
                    if samples[f].state.sign == samples[f - 1].state.sign
                    else _swap(side + "_")[:-1]
                )
                prev_heel, prev_toe = soles[f - 1][prev_side]
                a = samples[f].state.pose.foot(side)
                b = samples[f - 1].state.pose.foot(prev_side)
                planted = a.lift < 1e-6 and b.lift < 1e-6
                same_roll = (a.pitch > 0) == (b.pitch > 0) and (a.pitch < 0) == (b.pitch < 0)
                if planted and same_roll:
                    d = abs(_contact_x(samples[f], side) - _contact_x(samples[f - 1], prev_side))
                    if d > max_slide:
                        max_slide = d
                    if d > SLIDE_TOLERANCE:
                        slide_events.append((f, side, round(d, 3)))
                was = max(prev_heel[1], prev_toe[1]) >= -GROUND_EPS
                now_c = max(heel[1], toe[1]) >= -GROUND_EPS
                if now_c and not was:
                    landings[side].append(f)
        airborne.append(all(v < -0.6 for v in lows))

    # Joint validity, clamps, reach and leg flips.
    clamps = {}
    reach = 0.0
    flips = []
    thigh_len, shin_len, neck_len = [], [], []
    prev_off = {}
    for f, cf in enumerate(samples):
        s = cf.state
        for name in s.clamped:
            clamps[name] = clamps.get(name, 0) + 1
        for side in ("near", "far"):
            leg = s.legs[side]
            reach = max(reach, leg.reach_error)
            thigh_len.append(math.dist(leg.hip, leg.knee))
            shin_len.append(math.dist(leg.knee, leg.ankle))
            hx, hy = leg.hip
            ax, ay = leg.ankle
            kx, ky = leg.knee
            dx, dy = ax - hx, ay - hy
            d = math.hypot(dx, dy) or 1
            off = ((kx - hx) * dy - (ky - hy) * dx) / d * -1
            # Track the physical leg across mirror re-labelling; compare world-space offsets.
            key = side if cf.state.sign == samples[0].state.sign else _swap(side + "_")[:-1]
            off_w = off * cf.state.sign
            # A flip is a sign change of the knee offset between consecutive frames while
            # the leg is visibly bent on both frames (gradual foreshortening is allowed).
            if (
                key in prev_off
                and prev_off[key] * off_w < 0
                and min(abs(off_w), abs(prev_off[key])) > 1.0
            ):
                flips.append((f, side))
            prev_off[key] = off_w
        neck = s.joints["neck"]
        head = s.joints["head"]
        neck_len.append(math.dist((neck.x, neck.y), (head.x, head.y)))

    # Per-frame displacement of every joint (continuity) and section-boundary smoothness.
    disp = [0.0]
    for f in range(1, frames):
        same = samples[f].state.sign == samples[f - 1].state.sign
        disp.append(max(math.dist(pts[f][k], pts[f - 1][k if same else _swap(k)]) for k in pts[f]))
    boundaries = []
    for start, _end, label in sections:
        if start == 0:
            continue
        around = [disp[f] for f in range(max(1, start - 6), min(frames, start + 6)) if f != start]
        med = statistics.median(around) if around else 0
        boundaries.append(
            {
                "frame": start,
                "section": label,
                "max_joint_step_at_boundary": round(disp[start], 3),
                "median_step_nearby": round(med, 3),
                "ratio": round(disp[start] / med, 2) if med > 1e-6 else None,
            }
        )

    section_stats = []
    for start, end, label in sections:
        idx = range(start, end + 1)
        # Rig-space (canonical screen rotation) angles: counter-swing shows as negative.
        near_sh = [SIDE_OUT["near"] * samples[f].state.pose.near_arm.shoulder for f in idx]
        far_sh = [SIDE_OUT["far"] * samples[f].state.pose.far_arm.shoulder for f in idx]
        near_el = [samples[f].state.pose.near_arm.elbow for f in idx]
        far_el = [samples[f].state.pose.far_arm.elbow for f in idx]
        hip_ankle = [
            min(
                math.dist(samples[f].state.legs[s].hip, samples[f].state.legs[s].ankle)
                for s in ("near", "far")
            )
            for f in idx
        ]
        pelvis_x = [samples[f].state.pose.pelvis_x for f in idx]
        pelvis_h = [samples[f].state.pose.pelvis_height for f in idx]
        speeds = [abs(pelvis_x[i] - pelvis_x[i - 1]) for i in range(1, len(pelvis_x))]
        section_stats.append(
            {
                "frames": [start, end],
                "section": label,
                "actions": sorted({samples[f].action for f in idx}),
                "airborne_frames": sum(airborne[f] for f in idx),
                "landings": {s: [f for f in landings[s] if start <= f <= end] for s in landings},
                "near_shoulder_range": [round(min(near_sh), 2), round(max(near_sh), 2)],
                "far_shoulder_range": [round(min(far_sh), 2), round(max(far_sh), 2)],
                "elbow_range": [round(min(near_el + far_el), 2), round(max(near_el + far_el), 2)],
                "arm_shoulder_correlation": round(_corr(near_sh, far_sh), 3),
                "min_hip_ankle": round(min(hip_ankle), 2),
                "pelvis_height_range": [round(min(pelvis_h), 2), round(max(pelvis_h), 2)],
                "travel_units": round(pelvis_x[-1] - pelvis_x[0], 2),
                "max_speed_units_per_frame": round(max(speeds) if speeds else 0, 3),
                "max_joint_step": round(max(disp[f] for f in idx), 3),
                "expressions_eye_scale_range": [
                    round(min(samples[f].face.eye_scale for f in idx), 2),
                    round(max(samples[f].face.eye_scale for f in idx), 2),
                ],
            }
        )

    finite_ok = all(all(math.isfinite(c) for p in row.values() for c in p) for row in pts)
    summary = {
        "frames": frames,
        "all_joint_transforms_finite": finite_ok,
        "max_planted_contact_slide_units": round(max_slide, 4),
        "planted_slide_events_over_tolerance": len(slide_events),
        "max_ground_penetration_units": round(max(0.0, max_pen), 4),
        "max_leg_reach_error_units": round(reach, 4),
        "clamped_channel_frames": clamps,
        "knee_flip_events": flips,
        "thigh_projected_length_range": [round(min(thigh_len), 2), round(max(thigh_len), 2), THIGH],
        "shin_projected_length_range": [round(min(shin_len), 2), round(max(shin_len), 2), SHIN],
        "neck_head_distance_range": [round(min(neck_len), 2), round(max(neck_len), 2), NECK_LEN],
        "airborne_frames_total": sum(airborne),
        "max_joint_step_units": round(max(disp), 3),
        "blink_frames": sum(1 for cf in samples if cf.blink > 0.5),
    }
    return {
        "units": "character units (x2.3 logical px, x4.6 output px)",
        "tolerances": {
            "ground_contact": GROUND_EPS,
            "slide": SLIDE_TOLERANCE,
            "penetration": PENETRATION_TOLERANCE,
        },
        "summary": summary,
        "sections": section_stats,
        "boundaries": boundaries,
        "slide_events": slide_events[:50],
    }
