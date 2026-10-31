"""Read-only memory topology discovery. Missing controller data never implies unlimited RAM."""

import os
import platform
import re
from pathlib import Path, PurePosixPath

from reelforge.core.errors import OperationError

POLICIES = ("strict", "guest_procfs_fallback")
MIB = 1024 * 1024


def check_policy(policy: str) -> str:
    if policy not in POLICIES:
        raise OperationError("MEMORY_POLICY", f"Use one of {POLICIES}; no custom resource limits")
    return policy


def add_memory_policy_argument(parser) -> None:
    parser.add_argument(
        "--memory-policy",
        choices=POLICIES,
        default="strict",
        help="guest_procfs_fallback explicitly authorizes use of guest RAM when eligible; "
        "it never ignores a discoverable cgroup limit",
    )


def read_observation(path: str) -> dict:
    try:
        with Path(path).open() as handle:
            value = handle.read(131073)
        if len(value) > 131072:
            return {"status": "invalid", "error": "observation exceeds 128 KiB"}
        return {"status": "present", "value": value.strip()}
    except FileNotFoundError:
        return {"status": "missing"}
    except OSError as error:
        return {"status": "unreadable", "error": type(error).__name__}


def guest_checks(mem: dict, read) -> dict:
    """Necessary checks plus explicit operator assertion, not authenticated VM identity."""
    try:
        os_release = platform.freedesktop_os_release()
    except OSError:
        os_release = {}
    markers = {p: read(p) for p in ("/.dockerenv", "/run/.containerenv", "/run/systemd/container")}
    cpu = read("/proc/cpuinfo")
    dmi = read("/sys/class/dmi/id/product_name")
    hypervisor = cpu["status"] == "present" and bool(re.search(r"\bhypervisor\b", cpu["value"]))
    virtual_product = dmi["status"] == "present" and any(
        name in dmi["value"].lower()
        for name in ("kvm", "qemu", "virtual machine", "firecracker", "hvm domu", "bochs")
    )
    return {
        "ubuntu_24_04_x86_64": os_release.get("ID") == "ubuntu"
        and os_release.get("VERSION_ID") == "24.04"
        and platform.machine() == "x86_64",
        "four_affinity_cpus": len(os.sched_getaffinity(0)) == 4,
        "reported_ram_near_target": 7 * 1024**3 <= mem["MemTotal"] <= 8.5 * 1024**3,
        "no_guest_swap": mem["SwapTotal"] == 0,
        "no_known_container_markers": all(p["status"] == "missing" for p in markers.values()),
        "virtualization_evidence": hypervisor or virtual_product,
    }


def _absolute(value: str) -> PurePosixPath:
    if not value.startswith("/") or ".." in value.split("/"):
        raise ValueError("non-absolute or escaping cgroup path")
    return PurePosixPath(value)


def _unescape(value: str) -> str:
    return re.sub(r"\\(040|011|012|134)", lambda m: chr(int(m[1], 8)), value)


def _topology(membership: str, mountinfo: str, controllers: str) -> tuple[list, list, dict]:
    members, mounts, kernel = [], [], {}
    if not controllers.startswith("#subsys_name"):
        raise ValueError("missing kernel controller inventory header")
    for line in membership.splitlines():
        fields = line.split(":", 2)
        if len(fields) != 3 or not fields[0].isdigit():
            raise ValueError("invalid /proc/self/cgroup")
        members.append((fields[0], fields[1].split(",") if fields[1] else [], _absolute(fields[2])))
    if len({m[0] for m in members}) != len(members):
        raise ValueError("duplicate hierarchy memberships")
    for line in mountinfo.splitlines():
        before, separator, after = line.partition(" - ")
        a, b = before.split(), after.split()
        if not separator or len(a) < 6 or len(b) != 3:
            raise ValueError("invalid mountinfo record")
        mounts.append(
            {
                "root": _absolute(_unescape(a[3])),
                "point": _absolute(_unescape(a[4])),
                "fs": b[0],
                "options": set(a[5].split(",") + b[2].split(",")),
            }
        )
    if not mounts:
        raise ValueError("empty mount topology")
    for line in controllers.splitlines():
        if line.startswith("#"):
            continue
        f = line.split()
        if len(f) != 4 or not all(x.isdigit() for x in f[1:]) or f[3] not in {"0", "1"}:
            raise ValueError("invalid /proc/cgroups")
        if f[0] in kernel:
            raise ValueError("duplicate kernel controller")
        kernel[f[0]] = {"hierarchy": int(f[1]), "enabled": f[3] == "1"}
    return members, mounts, kernel


def observe_memory(*, policy: str = "strict") -> dict:
    check_policy(policy)
    probes, mem, constraints = {}, {}, []
    counters = dict.fromkeys(
        (
            "memory.max",
            "memory.current",
            "memory.peak",
            "memory.events",
            "memory.swap.max",
            "memory.swap.current",
            "cpu.max",
        )
    )
    result = {
        "host": mem,
        "cgroup_root": None,
        "cgroup": counters,
        "effective_available_bytes": 0,
        "memory_policy": policy,
        "fallback_enabled": policy == "guest_procfs_fallback",
        "fallback_used": False,
        "memory_source": "unavailable",
        "controller_state": "unknown",
        "constraints": constraints,
        "observations": probes,
        "errors": [],
        "limitations": [
            "Visible namespaces cannot prove absence of hidden ancestor limits.",
            "Guest availability may change suddenly with ballooning/external contention.",
            "Software RSS/reserve monitoring is not a dedicated memory cgroup.",
        ],
    }

    def read(path):
        if path not in probes:
            probes[path] = read_observation(path)
        return probes[path]

    def required(path):
        obs = read(path)
        if obs["status"] != "present":
            raise ValueError(f"{path}: {obs['status']}")
        return obs["value"]

    def optional(path):
        obs = read(path)
        if obs["status"] not in {"present", "missing"}:
            raise ValueError(f"{path}: {obs['status']}")
        return obs.get("value")

    def number(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise ValueError("invalid nonnegative controller value")
        return int(value)

    try:
        for line in required("/proc/meminfo").splitlines():
            f = line.split()
            if f and f[0] in {"MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"}:
                name = f[0][:-1]
                if name in mem or len(f) != 3 or f[2] != "kB":
                    raise ValueError("invalid or duplicate guest memory observation")
                mem[name] = number(f[1]) * 1024
        if set(mem) != {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"} or not (
            0 < mem["MemTotal"]
            and 0 <= mem["MemAvailable"] <= mem["MemTotal"]
            and 0 <= mem["SwapFree"] <= mem["SwapTotal"]
        ):
            raise ValueError("missing or inconsistent guest memory fields")
        members, mounts, kernel = _topology(
            required("/proc/self/cgroup"),
            required("/proc/self/mountinfo"),
            required("/proc/cgroups"),
        )
        result["kernel_memory_controller"] = kernel.get("memory")
        v1 = [m for m in members if "memory" in m[1]]
        v2 = [m for m in members if m[0] == "0" and not m[1]]
        memory_mounts = [m for m in mounts if m["fs"] == "cgroup" and "memory" in m["options"]]
        unified_mounts = [m for m in mounts if m["fs"] == "cgroup2"]
        if len(v1) > 1 or len(v2) > 1 or (v1 and memory_mounts and len(memory_mounts) != 1):
            raise ValueError("ambiguous controller topology")
        if bool(v1) != bool(memory_mounts) or bool(v2) != bool(unified_mounts):
            raise ValueError("controller membership/mount mismatch; possibly masked or unmounted")
        if len(unified_mounts) > 1:
            raise ValueError("multiple unified mounts; ambiguous view")
        selected = (
            (v1[0], memory_mounts[0], "v1")
            if v1
            else ((v2[0], unified_mounts[0], "v2") if v2 else None)
        )
        if v1 and (
            kernel.get("memory", {}).get("hierarchy") != int(v1[0][0])
            or not kernel.get("memory", {}).get("enabled")
        ):
            raise ValueError("v1 membership contradicts kernel inventory")
        if not v1 and kernel.get("memory", {}).get("hierarchy", 0) != 0:
            raise ValueError("unseen v1 memory hierarchy")
        if (
            v1
            and unified_mounts
            and "memory" in required(f"{unified_mounts[0]['point']}/cgroup.controllers").split()
        ):
            raise ValueError("memory advertised in both v1 and v2")
        advertised = False
        if selected:
            member, mount, version = selected
            if not member[2].is_relative_to(mount["root"]):
                raise ValueError("membership cannot be mapped to mount root")
            leaf = mount["point"] / member[2].relative_to(mount["root"])
            root = mount["point"]
            if any(m["point"].is_relative_to(root) and m is not mount for m in mounts):
                raise ValueError("overmounted controller view; possible masking")
            directories = [leaf, *leaf.parents[: len(leaf.parts) - len(root.parts)]]
            result["cgroup_root"] = str(leaf)
            result["controller_version"] = version
            for directory in directories:
                if Path(str(directory)).is_symlink():
                    raise ValueError("symlinked controller directory")
                if version == "v2":
                    names = required(f"{directory}/cgroup.controllers").split()
                    advertised |= "memory" in names
                    maximum = optional(f"{directory}/memory.max")
                    usage = optional(f"{directory}/memory.current")
                else:
                    maximum = required(f"{directory}/memory.limit_in_bytes")
                    usage = required(f"{directory}/memory.usage_in_bytes")
                    # Require hierarchy accounting to avoid silently missing parent limits.
                    if required(f"{directory}/memory.use_hierarchy") != "1":
                        raise ValueError("v1 nonhierarchical accounting unsupported")
                if (maximum is None) != (usage is None):
                    raise ValueError("partial memory controller observation")
                if maximum is not None:
                    limit = maximum if maximum == "max" and version == "v2" else number(maximum)
                    used = number(usage)
                    if isinstance(limit, int) and used > limit:
                        raise ValueError("usage exceeds limit; refuse inconsistent/over-limit view")
                    constraints.append({"path": str(directory), "limit": limit, "usage": used})
            if version == "v1":
                stats = dict(line.split() for line in required(f"{leaf}/memory.stat").splitlines())
                inherited = number(stats.get("hierarchical_memory_limit"))
                if inherited < min(c["limit"] for c in constraints):
                    raise ValueError("v1 hidden hierarchical limit; usage is not visible")
            for name in counters:
                value = optional(f"{leaf}/{name}") if version == "v2" else None
                counters[name] = int(value) if value is not None and value.isdigit() else value
            if version == "v1":
                counters["memory.max"], counters["memory.current"] = (
                    constraints[0]["limit"],
                    constraints[0]["usage"],
                )
                result["v1_oom_control"] = optional(f"{leaf}/memory.oom_control")
                result["v1_failcnt"] = optional(f"{leaf}/memory.failcnt")
        if constraints:
            if kernel.get("memory", {}).get("enabled") is False:
                raise ValueError("disabled kernel controller contradicts discovered limits")
            available = mem["MemAvailable"]
            for constraint in constraints:
                if constraint["limit"] != "max":
                    available = min(available, constraint["limit"] - constraint["usage"])
            result.update(
                effective_available_bytes=available,
                memory_source="guest_and_cgroup",
                controller_state="observable",
            )
        else:
            if any(
                value is not None for key, value in counters.items() if key.startswith("memory.")
            ):
                raise ValueError("memory telemetry exists without complete capacity accounting")
            # An enabled/bound controller without readable accounting is not an absent controller.
            if advertised or kernel.get("memory", {}).get("enabled", False):
                raise ValueError("memory controller enabled/advertised but accounting unavailable")
            if kernel.get("memory", {}).get("hierarchy", 0) != 0:
                raise ValueError("memory controller bound to an unseen hierarchy")
            result["controller_state"] = "unavailable_in_observed_guest"
            if policy == "guest_procfs_fallback":
                checks = guest_checks(mem, read)
                checks["ordinary_guest_root_filesystem"] = any(
                    m["point"] == PurePosixPath("/") and m["fs"] in {"ext4", "xfs", "btrfs"}
                    for m in mounts
                )
                result["guest_checks"] = checks
                if not all(checks.values()):
                    raise ValueError(
                        "guest fallback environment checks failed; inspect guest_checks"
                    )
                result.update(
                    effective_available_bytes=mem["MemAvailable"],
                    memory_source="guest_procfs",
                    fallback_used=True,
                )
            else:
                result["errors"].append(
                    "Memory controller unavailable; strict policy denies admission"
                )
    except (ValueError, OSError) as error:
        result["effective_available_bytes"] = 0
        result["memory_source"] = "unavailable"
        result["errors"].append(str(error))
    return result


def oom_counts(raw: str | None) -> dict[str, int]:
    if not isinstance(raw, str):
        return {}
    try:
        fields = [line.split() for line in raw.splitlines()]
        if any(len(f) != 2 or not f[1].isdigit() for f in fields):
            return {}
        parsed = {f[0]: int(f[1]) for f in fields}
        return parsed if len(parsed) == len(fields) else {}
    except ValueError:
        return {}
