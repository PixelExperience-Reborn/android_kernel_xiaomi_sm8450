#!/usr/bin/env python3
"""Validate a real, physically checked-out mondrian trial kernel BSP.

Usage after repo init/sync with aosp17_pe_mondrian_bsp_trial.xml:
  python3 kernel/xiaomi/sm8450/tools/verify_trial_workspace.py --root .

This checker deliberately lives in the PE kernel AUDIT repository; source
trials can copy it into a build tools directory before switching checkout.
It does not build, flash, sign or change any phone partition.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

SOURCE_PATHS = {
    "kernel": "kernel/xiaomi/sm8450",
    "modules": "kernel/xiaomi/sm8450-modules",
    "devicetrees": "kernel/xiaomi/sm8450-devicetrees",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_info(path):
    cmd = ["git", "-C", str(path), "rev-parse"]
    commit = subprocess.run(cmd + ["HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    tree = subprocess.run(cmd + ["HEAD^{tree}"], check=True, capture_output=True, text=True).stdout.strip()
    return commit, tree


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest()


def verify_sources(root, lock):
    sources = {source["role"]: source for source in lock["sources"]}
    report = {"device": "mondrian", "android": "AOSP 17", "source_verified": False,
              "kernel_built": False, "modules_built": False, "dtbo_built": False,
              "boot_qualified": False, "entries": []}
    require(set(sources) == set(SOURCE_PATHS), "source lock roles differ from checkout layout")
    for role, rel in SOURCE_PATHS.items():
        path = root / rel
        source = sources[role]
        require(path.is_dir(), f"missing {role} checkout at {path}")
        commit, tree = git_info(path)
        require(commit == source["commit_sha"], f"{role} HEAD wrong: {commit}")
        require(tree == source["root_tree_sha"], f"{role} root tree wrong: {tree}")
        for pinned in source["files"]:
            p = path / pinned["path"]
            require(p.is_file(), f"{role} missing {pinned['path']}")
            data = p.read_bytes()
            require(git_blob(data) == pinned["blob_sha"], f"{role} Git blob mismatch: {pinned['path']}")
            text = data.decode("utf-8")
            for needle in pinned["contains"]:
                require(needle in text, f"{role} content assertion missing: {pinned['path']} {needle!r}")
        report["entries"].append({"role": role, "path": rel, "commit": commit,
                                  "root_tree": tree, "pinned_blobs_verified": len(source["files"])})
    kernel = root / SOURCE_PATHS["kernel"]
    for f in ("scripts/kconfig/merge_config.sh", "scripts/config", "arch/arm64/configs/gki_defconfig",
              "arch/arm64/configs/vendor/waipio_GKI.config",
              "arch/arm64/configs/vendor/xiaomi_GKI.config",
              "arch/arm64/configs/vendor/mondrian_GKI.config",
              "arch/arm64/configs/vendor/debugfs.config",
              "android/abi_gki_aarch64_qcom"):
        require((kernel / f).is_file(), f"kernel configuration/KMI file missing: {f}")
    dts = root / SOURCE_PATHS["devicetrees"]
    for f in ("qcom/mondrian-sm8475.dtsi", "qcom/Makefile", "qcom/display/Kbuild",
              "qcom/camera/config/waipio.mk"):
        require((dts / f).is_file(), f"DT source missing: {f}")
    layout = lock["build_layout"]
    report["required_unresolved_workspace"] = [
        {"name": "matching Android Common Kernel", "path": "common",
         "selected": layout["ack_kernel_commit"] is not None},
        {"name": "LLVM/Clang toolchain", "path": "prebuilts/clang/host/linux-x86",
         "selected": layout["compiler_revision"] is not None},
        {"name": "Qualcomm external DTC", "path": "external/dtc",
         "selected": layout["host_dtc_revision"] is not None},
    ]
    require(not any(e["selected"] for e in report["required_unresolved_workspace"]),
            "unreviewed toolchain or ACK selection in source-only trial")
    report["source_verified"] = True
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--lock", type=Path, default=Path(__file__).resolve().parents[1] /
                        "lf52406-bsp-trial-lock.json")
    parser.add_argument("--report", type=Path, help="Write machine-readable source-only report")
    args = parser.parse_args()
    root = args.root.resolve()
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    report = verify_sources(root, lock)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"[PASS] real checked-out kernel, modules and DT: {sum(x['pinned_blobs_verified'] for x in report['entries'])} exact Git blobs")
    print("[BLOCKED] kernel build: matching ACK, toolchain, KMI, module outputs and real device still unselected")
    print("[BLOCKED] Android17 QPR1+: Linux/GKI 5.10 unsupported per current AOSP matrix")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, UnicodeError, subprocess.CalledProcessError,
            json.JSONDecodeError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
