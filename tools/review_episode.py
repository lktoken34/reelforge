"""Collect existing episode evidence and decode contact frames; never rerender a movie."""

import json
from fractions import Fraction
from pathlib import Path

from review_geometry import sheet

from reelforge.audio.processing import command
from reelforge.audio.registry import AudioRegistry
from reelforge.episodes.contract import inspect_episode, load_episode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase8"


def main():
    report = json.loads((OUT / "demo/report.json").read_text())
    if not report["media_verified"] or not report["published"]:
        raise RuntimeError("No verified published demo; preserve the failed job without a retry")
    plan = load_episode(ROOT / "examples/episodes/relay_to_shelter.json")
    registry = AudioRegistry(ROOT / "assets/audio")
    scratch = ROOT / "outputs/phase8-review"
    scratch.mkdir(exist_ok=False)
    cells = []
    inspections = []
    for index, segment in enumerate(plan.segments):
        for local in (0, 45, 89):
            f = index * 90 + local
            path = scratch / f"frame_{f:03}.png"
            command(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-v",
                    "error",
                    "-threads",
                    "1",
                    "-i",
                    str(OUT / "demo/reel.mp4"),
                    "-vf",
                    f"select=eq(n\\,{f})",
                    "-frames:v",
                    "1",
                    "-threads:v",
                    "1",
                    "-n",
                    str(path),
                ]
            )
            cells.append((f"{segment.id} / global frame {f}", path))
            inspections.append(inspect_episode(plan, registry, f))
    sheet(cells, OUT / "episode_contact_sheet.png")
    (OUT / "selected_frame_inspections.json").write_text(json.dumps(inspections, indent=2) + "\n")
    (OUT / "compiled_storyboards.json").write_text(
        json.dumps(
            [
                {
                    "id": s.id,
                    "blocking": json.loads(s.storyboard.blocking_json),
                    "direction": json.loads(s.storyboard.direction_json),
                }
                for s in plan.segments
            ],
            indent=2,
        )
        + "\n"
    )
    ticks = report["streams"]["video_pts_ticks"]
    base = Fraction(report["streams"]["metadata"]["streams"][0]["time_base"])
    boundaries = []
    for f in range(90, plan.frames, 90):
        assert ticks[f] * base == Fraction(f, 30) and (ticks[f] - ticks[f - 1]) * base == Fraction(
            1, 30
        )
        boundaries.append(
            {
                "frame": f,
                "before_pts": str(ticks[f - 1] * base),
                "after_pts": str(ticks[f] * base),
                "sample": f * 1600,
            }
        )
    av = report["audio_verification"]
    summary = {
        "frames": plan.frames,
        "seconds": plan.frames / 30,
        "aspect_ratio": "9:16",
        "dimensions": [720, 1280],
        "streams": ["H.264/yuv420p", "AAC-LC/48000/stereo"],
        "video_pts_exact": True,
        "cuts": boundaries,
        "video_bitstream_unchanged": av["h264_bitstream_unchanged"],
        "all_decoded_video_hashes_equal": report["verification"]["decoded_rgb_sha256"]
        == report["video_report"]["verification"]["decoded_rgb_sha256"],
        "effective_samples_per_channel": av["effective_samples_per_channel"],
        "decoded_samples_per_channel": av["raw_decoded_samples_per_channel"],
        "padding_samples": av["terminal_padding_samples"],
        "cue_timing": av["cue_timing"],
        "audible_drift_samples": av["audible_drift_samples"],
        "audible_drift_ms": av["audible_drift_samples"] / 48,
        "mix": report["mix"]["statistics"],
        "decoded_pcm": av["decoded_pcm"],
        "original_job_success": report["success"],
        "transaction_clean_at_return": report["transaction_clean"],
        "retired_path_now_present": Path(report["transaction_path"]).exists(),
        "scope": "Later restoration is failure evidence; original job statuses preserved; no sweep",
        "deployment_gate_approved": False,
    }
    (OUT / "technical_verification.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in [
                    "frames",
                    "effective_samples_per_channel",
                    "padding_samples",
                    "retired_path_now_present",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
