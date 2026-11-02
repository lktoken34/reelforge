"""Offline evidence summary; never runs native tools, repairs paths or changes old reports."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase7b1"


def summarize(path):
    trace = json.loads(path.read_text())
    events = trace["events"]
    previous = {}
    transitions = []
    for index, event in enumerate(events):
        if event["event"] != "snapshot":
            continue
        for name, state in event["paths"].items():
            before = previous.get(name)
            if state["retired"] and state["path"] is not None and before and before[1] is None:
                a = before[0]
                entering = [e for e in events[:index] if e["event"] == "native_enter"]
                child = [e for e in events[:index] if e["event"] == "native_constructor_return"]
                notify = [
                    e
                    for e in events
                    if e["event"] == "fanotify"
                    and Path(name).name in e["names"]
                    and e["mask"] & 0x100
                ]
                deleting = [
                    e
                    for e in events
                    if e["event"] == "fanotify"
                    and Path(name).name in e["names"]
                    and e["mask"] & 0x200
                ]
                transitions.append(
                    {
                        "path": name,
                        "last_absent_index": a,
                        "first_present_index": index,
                        "last_absent_ns": events[a]["monotonic_ns"],
                        "first_present_ns": event["monotonic_ns"],
                        "observation_window_ms": (event["monotonic_ns"] - events[a]["monotonic_ns"])
                        / 1e6,
                        "original_inode": state["original"],
                        "restored_inode": state["path"],
                        "original_unlinked_inode": state.get("original_fd"),
                        "stable_parent_fd_identity": all(
                            events[a]["parent_fd"][k] == event["parent_fd"][k]
                            for k in ("dev", "ino")
                        ),
                        "stable_mount_view": events[a]["mounts"] == event["mounts"],
                        "active_native_argv": entering[-1]["argv"] if entering else None,
                        "active_native_pid": child[-1]["pid"] if child else None,
                        "kernel_create_notifications": notify,
                        "kernel_delete_notifications": deleting,
                        "python_mutation_events_in_window": [
                            e
                            for e in events[a : index + 1]
                            if e["event"] == "python_mutation_audit"
                        ],
                    }
                )
            previous[name] = (index, state["path"])
    children = next((e["processes"] for e in events if e["event"] == "all_children_final"), [])
    tests = [e for e in events if e["event"] == "targeted_test_return"]
    snapshots = [e for e in events if e["event"] == "snapshot"]
    return {
        "trace": str(path.relative_to(ROOT)),
        "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "mode_label_caveat": (
            "Early mode field was hardcoded; module inventory determines engine independence"
        ),
        "reelforge_modules_loaded": trace["reelforge_modules_loaded"],
        "identity": trace["identity"],
        "complete": trace["complete"],
        "restorations": transitions,
        "native_children": len(children),
        "all_native_children_reaped_and_groups_absent": bool(children)
        and all(
            p["waitpid_reports_no_child"]
            and p["process_group_absent"]
            and p["stdout_closed"]
            and p["stderr_closed"]
            for p in children
        ),
        "native_process_records": children,
        "test_exit_code": tests[-1]["exit_code"] if tests else None,
        "retired_paths_currently_present": {
            name: (Path(trace["probe_root"]) / name).exists() for name in snapshots[-1]["paths"]
        },
        "memory": next((e["report"] for e in events if e["event"] == "resource_report"), None),
    }


def main():
    inventories = {}
    for name in (
        "control",
        "native-control",
        "site-control",
        "integrated-trace",
        "legacy-trace",
        "writer-trace",
        "wav-followup-control",
        "pipe-control",
        "paced-pipe",
        "decoded-pipe",
        "confined-trace",
        "final-confined-trace",
    ):
        source = ROOT / f"outputs/phase7b1-{name}/trace.json"
        target = OUT / (name + ".json")
        target.write_bytes(source.read_bytes())
        inventories[name] = summarize(target)
    inventories["mp4-control"] = summarize(OUT / "mp4-control/trace.json")
    for name in ("legacy-trace", "writer-trace", "confined-trace", "final-confined-trace"):
        (OUT / (name + "-junit.xml")).write_bytes(
            (ROOT / f"outputs/phase7b1-{name}/targeted.xml").read_bytes()
        )
    guards = [
        json.loads(line)
        for line in (ROOT / "outputs/phase7b1-final-confined-trace/native_restrictions.jsonl")
        .read_text()
        .splitlines()
    ]
    (OUT / "native_restrictions.jsonl").write_text("".join(json.dumps(g) + "\n" for g in guards))
    controlled = inventories["final-confined-trace"]
    child_pids = {p["pid"] for p in controlled["native_process_records"]}
    guard_pids = {g["pid"] for g in guards}
    verified = (
        len(guards) == len(child_pids) == 55
        and child_pids == guard_pids
        and all(
            g["denied"] == g["denial_checks"] == 10
            and g["no_new_privs"] == 1
            and g["seccomp_mode"] == 2
            for g in guards
        )
    )
    parent = controlled["identity"]["pid"]
    conditions = [
        all(
            t["original_unlinked_inode"]["nlink"] == 0
            and t["original_inode"]["ino"] != t["restored_inode"]["ino"]
            and t["stable_parent_fd_identity"]
            and t["stable_mount_view"]
            and t["kernel_create_notifications"]
            and all(n["pid"] == 0 for n in t["kernel_create_notifications"])
            and t["kernel_delete_notifications"]
            and all(n["pid"] == parent for n in t["kernel_delete_notifications"])
            for t in controlled["restorations"]
        ),
        controlled["all_native_children_reaped_and_groups_absent"],
        verified,
    ]
    result = {
        "base_commit": "a2587e7f42a4260aa2b5ed2941b15b05c6370d81",
        "investigation": inventories,
        "confined_child_guard_verified": verified,
        "guard_scope": (
            "Diagnostic child and inherited descendants only; no production or host policy changes"
        ),
        "external_actor_isolated_from_traced_engine_processes": bool(controlled["restorations"])
        and all(conditions),
        "specific_external_writer_identity": None,
        "host_cleanup_gate": "blocked",
        "full_suites_run": 0,
        "original_phase7b_movies_regenerated": False,
        "result_scope": (
            "Recreation outside traced Python parent and its 55 confined native children; "
            "host service/mechanism remains unidentified"
        ),
    }
    assert result["external_actor_isolated_from_traced_engine_processes"]
    (OUT / "investigation_summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "external_actor_isolated": True,
                "guarded_children": len(guards),
                "confined_restorations": len(controlled["restorations"]),
                "original_tests_changed": False,
                "full_suites_run": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
