"""Review two independent CLI audio renders, preserving the original silent reference."""

import argparse
import json
from html import escape
from pathlib import Path

from reelforge.audio.processing import command, ffmpeg
from reelforge.audio.registry import digest
from reelforge.contracts.project import project_digest
from reelforge.core.errors import OperationError
from reelforge.resources.monitor import JobMonitor

ROOT = Path(__file__).resolve().parents[1]


def waveform_svg(report: dict) -> str:
    verification = report["audio_verification"]
    tracks = verification["cue_timing"]
    total = report["frames_written"] * 1600
    duration = report["frames_written"] / 30
    x0, width = 230, 1000
    y0 = 100 + 55 * len(tracks)
    reference_y = y0 + 95
    decoded_y = reference_y + 125
    height = decoded_y + 105
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="{height}">',
        f'<rect width="1280" height="{height}" fill="#142c34"/>',
        '<text x="30" y="34" fill="#eed7ab" font-size="21">'
        f"{escape(report['story']['title'])}</text>",
        '<text x="30" y="58" fill="#a8bcb1" font-size="14">'
        "Planned cue windows and decoded PCM peak envelopes</text>",
    ]
    colors = ("#d5b47a", "#8fa47c", "#64908a", "#8e9291", "#afa071")
    for i, track in enumerate(tracks):
        y = 85 + i * 55
        start = track["scheduled_start_sample"]
        length = track["effective_samples"]
        x = x0 + width * start / total
        w = width * length / total
        elements.extend(
            [
                f'<text x="30" y="{y + 5}" fill="#eed7ab" font-size="14">'
                f"{escape(track['asset_id'][:26])}</text>",
                f'<text x="30" y="{y + 23}" fill="#a8bcb1" font-size="12">'
                f"frame {track['start_frame']} / sample {start}</text>",
                f'<rect x="{x:.3f}" y="{y - 10}" width="{w:.3f}" height="24" fill="{colors[i]}"/>',
            ]
        )
    for frame in [s["start_frame"] for s in report["story"]["shots"]] + [report["frames_written"]]:
        x = x0 + width * frame / report["frames_written"]
        anchor = "end" if frame == report["frames_written"] else "start"
        elements.extend(
            [
                f'<line x1="{x}" x2="{x}" y1="75" y2="{decoded_y + 45}" '
                'stroke="#647c78" stroke-dasharray="4 5"/>',
                f'<text x="{x}" y="{y0}" fill="#eed7ab" text-anchor="{anchor}" font-size="13">'
                f"{frame} / {frame / 30:g}s</text>",
            ]
        )
    wave = verification["waveform"]
    peak = max(wave["reference_peak_envelope"])
    for name, key, y, color in (
        ("Reference PCM", "reference_peak_envelope", reference_y, "#d5b47a"),
        ("Decoded AAC", "decoded_peak_envelope", decoded_y, "#8fbbb1"),
    ):
        bins = wave[key]
        points = []
        for i, value in enumerate(bins):
            x = x0 + width * i * wave["bin_samples"] / total
            points.append((x, y - value / peak * 40))
        for i in range(len(bins) - 1, -1, -1):
            x = x0 + width * i * wave["bin_samples"] / total
            points.append((x, y + bins[i] / peak * 40))
        coordinates = " ".join(f"{x:.2f},{yy:.2f}" for x, yy in points)
        elements.extend(
            [
                f'<text x="30" y="{y}" fill="#eed7ab" font-size="15">{name}</text>',
                f'<line x1="{x0}" x2="{x0 + width}" y1="{y}" y2="{y}" stroke="#536e6b"/>',
                f'<polygon points="{coordinates}" fill="{color}" opacity=".85"/>',
            ]
        )
    tolerance = verification["aac_tolerance_ms"]
    elements.extend(
        [
            f'<text x="30" y="{decoded_y + 75}" fill="#a8bcb1" font-size="13">'
            f"{duration:g}s / 48 kHz stereo; 50 ms plot bins. "
            f"Audible timing checked at sample resolution, tolerance {tolerance:.3f} ms.</text>",
            "</svg>",
        ]
    )
    return "\n".join(elements) + "\n"


def review(first_dir: Path, repeat_dir: Path) -> dict:
    first = json.loads((first_dir / "report.json").read_text())
    second = json.loads((repeat_dir / "report.json").read_text())
    if project_digest(first["story"]) != project_digest(second["story"]):
        raise OperationError("AUDIO_REVIEW", "Repeat manifests differ")
    a, b = first["audio_verification"], second["audio_verification"]
    comparison = {
        "same_native_version": first["audio_native_version"] == second["audio_native_version"],
        "expected_pcm_sha256_equal": first["mix"]["statistics"]["sha256"]
        == second["mix"]["statistics"]["sha256"],
        "decoded_pcm_sha256_equal": a["decoded_pcm"]["sha256"] == b["decoded_pcm"]["sha256"],
        "all_video_frames_equal": first["verification"]["decoded_rgb_sha256"]
        == second["verification"]["decoded_rgb_sha256"],
        "all_source_frames_equal": first["source_surface_sha256"]
        == second["source_surface_sha256"],
        "cue_timing_equal": a["cue_timing"] == b["cue_timing"],
        "scope": "Independent CLI processes, same build; AAC container byte identity not promised",
    }
    if not all(value for key, value in comparison.items() if key != "scope"):
        raise OperationError("AUDIO_REPEAT", "Same-build decoded video/PCM or cue timing differs")
    original_report = json.loads((ROOT / "artifacts/phase4a/report.json").read_text())
    original_video = ROOT / "artifacts/phase4a/story.mp4"
    compatibility = {
        "approved_base_commit": "fd14320355f442f5fe9c59043b19a6009bd0f482",
        "original_silent_path": "artifacts/phase4a/story.mp4",
        "original_silent_sha256": digest(original_video),
        "all_360_decoded_video_frames_match_original": first["verification"]["decoded_rgb_sha256"]
        == original_report["verification"]["decoded_rgb_sha256"],
        "all_360_source_frames_match_original": first["source_surface_sha256"]
        == original_report["source_surface_sha256"],
        "h264_copied_without_reencoding": a["h264_bitstream_unchanged"],
        "all_video_presentation_timestamps_preserved": a["video_pts_unchanged"],
    }
    if not all(
        compatibility[k]
        for k in (
            "all_360_decoded_video_frames_match_original",
            "all_360_source_frames_match_original",
        )
    ):
        raise OperationError("AUDIO_COMPATIBILITY", "Approved 12-second silent story changed")
    (first_dir / "repeat_consistency.json").write_text(json.dumps(comparison, indent=2) + "\n")
    (first_dir / "silent_compatibility.json").write_text(json.dumps(compatibility, indent=2) + "\n")
    (first_dir / "sync_report.json").write_text(json.dumps(a, indent=2) + "\n")
    (first_dir / "repeat_report.json").write_text(json.dumps(second, indent=2) + "\n")
    svg = first_dir / "audio_timeline.svg"
    svg.write_text(waveform_svg(first))
    with JobMonitor(workspace=first_dir) as monitor:
        command(
            ffmpeg()
            + [
                "-protocol_whitelist",
                "file",
                "-i",
                str(svg),
                "-frames:v",
                "1",
                "-threads:v",
                "1",
                "-y",
                str(first_dir / "audio_timeline.png"),
            ],
            cancelled=monitor.cancelled,
        )
    (first_dir / "visualization_report.json").write_text(
        json.dumps(monitor.report(), indent=2) + "\n"
    )
    retained = {
        str(directory): [str(p) for p in directory.glob(".reelforge-audio-*")]
        for directory in (first_dir, repeat_dir)
    }
    cleanup = {
        "passed": not any(retained.values()),
        "retained_transactions": retained,
        "scope": "Post-repeat and post-visualization filesystem check; no prior-job sweep",
    }
    (first_dir / "cleanup_report.json").write_text(json.dumps(cleanup, indent=2) + "\n")
    comparison["cleanup_gate_passed"] = cleanup["passed"]
    comparison["phase4b_accepted"] = False
    (first_dir / "repeat_consistency.json").write_text(json.dumps(comparison, indent=2) + "\n")
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repeat-dir", type=Path, required=True)
    args = parser.parse_args()
    result = review(args.output_dir.resolve(), args.repeat_dir.resolve())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
