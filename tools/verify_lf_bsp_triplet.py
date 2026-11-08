#!/usr/bin/env python3
"""Fail-closed, immutable three-repository mondrian BSP trial provenance.

Offline = validate selection policy and source pins, online = verify real Git
commit/tree and blob data. Neither mode compiles or qualifies a shipping kernel.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "lf52406-bsp-trial-lock.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
ROLES = {"kernel", "modules", "devicetrees"}


def require(test, message):
    if not test:
        raise ValueError(message)


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + bytes([0]) + raw).hexdigest()


def validate_lock(lock):
    require(lock["schema_version"] == 1, "unsupported lock schema")
    require(lock["device"] == "mondrian" and lock["soc"] == "SM8475", "only mondrian in scope")
    require(lock["android"] == "AOSP 17", "wrong AOSP base")
    require(lock["status"] == "TRIAL_SOURCE_ONLY_NOT_SELECTED_FOR_RELEASE", "trial falsely promoted")
    found = {s["role"]: s for s in lock["sources"]}
    require(len(lock["sources"]) == len(found) == 3 and set(found) == ROLES,
            "kernel/modules/DT source set incomplete")
    for name, source in found.items():
        require(source["repository"].startswith("LF52406/android_kernel_xiaomi_sm8450"),
                f"unexpected unreviewed trial source: {name}")
        require(not source["materialized_in_pe"],
                f"actual source import cannot be inferred: {name}")
        for field in ("commit_sha", "root_tree_sha"):
            require(bool(SHA.fullmatch(source[field])), f"bad immutable SHA: {field}")
        require(source["commit_sha"] != source["root_tree_sha"], "commit mistaken for tree")
        files = source["files"]
        require(files and len(files) == len({f["path"] for f in files}), "missing/duplicate file pins")
        for f in files:
            require(bool(SHA.fullmatch(f["blob_sha"])), "bad Git blob SHA")
            path = f["path"]
            require(path and not path.startswith("/") and ".." not in Path(path).parts
                    and chr(92) not in path, "unsafe source path")
            require(f["contains"] and all(isinstance(x, str) and x for x in f["contains"]),
                    "no pinned content assertions")
    links = lock.get("source_links", [])
    require(len(links) == 1, "expected a single pinned external DTS source symlink")
    link = links[0]
    require(link["role"] == "kernel" and
            link["path"] == "arch/arm64/boot/dts/vendor" and
            link["target"] == "../../../../../sm8450-devicetrees" and
            bool(SHA.fullmatch(link["git_blob_sha"])),
            "unreviewed kernel DT symlink/target")
    layout = lock["build_layout"]
    require(layout["kernel_build_config"] == "msm-kernel/build.config.msm.waipio",
            "Qualcomm build config not pinned")
    require(layout["ack_checkout"] == "common", "ACK root not specified")
    require(layout["msm_kernel_checkout"] == "msm-kernel", "MSM kernel root not specified")
    for key in ("compiler_revision", "ack_kernel_commit", "build_tools_commit", "host_dtc_revision"):
        require(layout[key] is None, f"untested {key} must remain unselected")
    expected = {"vendor/waipio_GKI.config", "vendor/xiaomi_GKI.config",
                "vendor/mondrian_GKI.config", "vendor/debugfs.config", "gki_defconfig"}
    require(set(layout["device_config_fragments"]) == expected, "defconfig fragment drift")
    conflict = lock["known_conflicts"]
    require(conflict["standalone_qualcomm_boot_header"] == 3 and
            conflict["rom_target_board_header_reference"] == 4 and
            not conflict["boot_header_layout_resolved"], "unreviewed boot header equivalence")
    require(conflict["goodix_manufacturer_dt_compatible"] != conflict["mondrian_dt_compatible"]
            and not conflict["touch_driver_replacement_approved"], "unsafe Goodix port assumption")
    require(not any(lock["gates"].values()), "BSP build/release gate prematurely enabled")
    require(not lock["android17_policy"]["gki_5_10_supported_on_qpr1_plus"],
            "AOSP17 QPR1+ does not support this legacy GKI")
    # Latest Google Android Clang is a diagnostic candidate for this legacy
    # Qualcomm 5.10 source. Never infer GKI/KMI production compatibility.
    diag = lock["diagnostic_android_clang"]
    require(diag["source_repository"] ==
            "https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86",
            "compiler is not the official Android prebuilt repository")
    require(diag["source_commit_sha"] == "c9ed23e2ba198658b630d4b10e09fa980cd43119",
            "compiler checkout is not pinned to reviewed Google commit")
    require(diag["source_root_tree_sha"] == "e78fb6d4e4c88779483d63fca708f43153ba673d",
            "compiler root tree changed without review")
    require(diag["path"] == "clang-r614150" and diag["llvm_major"] == 23,
            "expected modern Android LLVM23 diagnostic toolchain")
    require(diag["strict_frame_warnings_required"] and not diag["production_approved"],
            "diagnostic compiler incorrectly marked ready for release")
    require(diag["aosp17_platform_clang_unmodified"], "platform compiler modified without audit")
    require(diag["qualcomm_module_symvers_compatible"] is None and
            diag["kernel_runtime_booted"] is None,
            "unverified kernel module or boot status asserted")
    return found


def github_get(url):
    headers = {"User-Agent": "PE-Reborn-mondrian-BSP-trial-check"}
    if os.getenv("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read()


def verify_online(lock):
    sources = validate_lock(lock)
    for role in sorted(sources):
        source = sources[role]
        repo, commit = source["repository"], source["commit_sha"]
        metadata = json.loads(github_get(f"https://api.github.com/repos/{repo}/git/commits/{commit}"))
        require(metadata.get("sha") == commit, f"{role}: commit identity changed")
        require(metadata.get("tree", {}).get("sha") == source["root_tree_sha"],
                f"{role}: expected root tree does not match commit")
        print(f"[PASS] {role} Git commit + tree {commit[:12]}")
        for f in source["files"]:
            path = quote(f["path"], safe="/")
            raw = github_get(f"https://raw.githubusercontent.com/{repo}/{commit}/{path}")
            require(git_blob(raw) == f["blob_sha"], f"{role}: {path} blob mismatch")
            text = raw.decode("utf-8")
            for needle in f["contains"]:
                require(needle in text, f"{role}: expected source evidence missing in {path}: {needle}")
            print(f"[PASS] {role}/{path} Git blob")
    # A Git symlink is stored as a blob of its target path, not as a DTS file.
    link = lock["source_links"][0]
    source = sources[link["role"]]
    raw = github_get(
        f"https://raw.githubusercontent.com/{source['repository']}/{source['commit_sha']}/{link['path']}"
    )
    require(git_blob(raw) == link["git_blob_sha"], "kernel external DT symlink Git blob changed")
    require(raw.decode("utf-8") == link["target"], "kernel external DT symlink retargeted")
    print("[PASS] kernel DTS vendor symlink points to sibling sm8450-devicetrees")
    print("[PASS] pinned trial source provenance (NOT compiled kernel/modules/DTBO)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="Read-only check of exact public source objects")
    args = parser.parse_args()
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    sources = validate_lock(lock)
    print(f"[PASS] immutable trial source lock, roles: {','.join(sorted(sources))}")
    if args.online:
        verify_online(lock)
    else:
        print("[INFO] offline-only, no live GitHub commit/file validation (use --online)")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, UnicodeError, json.JSONDecodeError) as err:
        print(f"[FAIL] {err}", file=sys.stderr)
        sys.exit(1)
