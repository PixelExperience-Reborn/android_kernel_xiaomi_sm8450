#!/usr/bin/env python3
"""Fail-closed OEM provenance and API-gap probe for mondrian Xiaomi Display.

The Xiaomi sample is a READ-ONLY comparison from another device, never an
implementation or a substitute for original mondrian factory DTBO/vendor_boot.
A successful probe explicitly DOES NOT authorize AOSP17 product activation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

DEVICE = "mondrian"
KERNEL_VERSION = "5.10.81"
OEM_REFERENCE_REPO = "MiCode/vendor_opensource_display-drivers"
OEM_REFERENCE_BRANCH = "bsp-vermeer-t-oss"
OEM_REFERENCE_COMMIT = "c696b28150245a9ddd1f2701f071e4b580b44ce2"
OEM_BLOBS = {
    "msm/Kbuild": "38ab5fbddacaee8bc0576475d1cd58d81ff47566",
    "msm/mi_disp/mi_disp_lhbm.c": "4b6a266f4e9feee11d4a9071b3c5a67277f141e1",
    "msm/mi_disp/mi_disp_feature.c": "14136033374c4c8ea78dfbd6342aff4ca98b718a",
    "include/uapi/display/drm/mi_disp.h": "545952d8c9ce572a4de1a893b383a77d8f83ecf9",
}
QUALCOMM_BLOBS = {
    "techpack/display/msm/Kbuild": "ec664f1b1b5c575a76981e3df1b010c95399cdd4",
    "techpack/display/msm/dsi/dsi_panel.c": "df552d653b86e468c08eced977c61c6745d3750a",
}
REQUIRED_OEM_TOKENS = {
    "msm/Kbuild": (
        "mi_disp/mi_disp_core.o", "mi_disp/mi_disp_lhbm.o",
        "mi_disp/mi_disp_feature.o"),
    "msm/mi_disp/mi_disp_lhbm.c": (
        "mi_disp_lhbm_fod_thread_create", "mi_disp_lhbm_fod_enabled",
        "LHBM_TARGET_BRIGHTNESS_WHITE_1000NIT"),
    "msm/mi_disp/mi_disp_feature.c": (
        "mi_disp_feature_attach_display", "mi_disp_lhbm_fod_thread_create",
        "MI_DISP_EVENT_FOD"),
    "include/uapi/display/drm/mi_disp.h": (
        "MI_DISP_IOCTL_SET_LOCAL_HBM", "MI_DISP_IOCTL_REGISTER_EVENT",
        "MI_DISP_EVENT_FOD", "LOCAL_HBM_UI_READY"),
}


class SourceAuditError(RuntimeError):
    pass


def source_blob_sha(source):
    payload = source.read_bytes()
    header = b"blob " + str(len(payload)).encode("ascii") + b"\\x00"
    return hashlib.sha1(header + payload).hexdigest()


def verify_pinned_blobs(root, expected, label):
    if not root.is_dir():
        raise SourceAuditError(label + " source tree is missing")
    for relative, checksum in expected.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise SourceAuditError(label + " missing regular source: " + relative)
        measured = source_blob_sha(path)
        if measured != checksum:
            raise SourceAuditError(
                f"{label} source drift {relative}: expected {checksum}, got {measured}")


def verify_oem_reference(root):
    if not (root / ".git").exists():
        raise SourceAuditError("read-only Xiaomi source must be a real Git checkout")
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SourceAuditError("cannot verify OEM reference Git revision") from exc
    if sha != OEM_REFERENCE_COMMIT:
        raise SourceAuditError(
            f"wrong Xiaomi OEM reference commit: {sha}, required {OEM_REFERENCE_COMMIT}")
    verify_pinned_blobs(root, OEM_BLOBS, "Xiaomi")
    for relative, tokens in REQUIRED_OEM_TOKENS.items():
        content = (root / relative).read_text(encoding="utf-8")
        for token in tokens:
            if token not in content:
                raise SourceAuditError(
                    f"Xiaomi reference ABI token absent from {relative}: {token}")
    return sha


def inspect_mondrian_kernel(kernel):
    verify_pinned_blobs(kernel, QUALCOMM_BLOBS, "Qualcomm")
    makefile = (kernel / "Makefile").read_text(encoding="utf-8")
    if "VERSION = 5" not in makefile or "PATCHLEVEL = 10" not in makefile or (
            "SUBLEVEL = 81" not in makefile):
        raise SourceAuditError("expected unchanged Xiaomi Linux 5.10.81")
    if not (kernel / "arch/arm64/configs/vendor/mondrian_GKI.config").is_file():
        raise SourceAuditError("mondrian-specific OEM kernel configuration missing")
    selected = kernel / "techpack/display"
    kbuild = (selected / "msm/Kbuild").read_text(encoding="utf-8")
    # We only certify the current absent interface. Any future integration
    # requires a separate reviewed source/KMI/hardware milestone.
    if (selected / "msm/mi_disp").exists() or (
            selected / "include/uapi/display/drm/mi_disp.h").exists() or (
            "mi_disp/" in kbuild):
        raise SourceAuditError(
            "new Xiaomi Display implementation detected: requalify its UAPI, "
            "build/ABI and mondrian hardware before changing production gate")
    return {
        "device": DEVICE,
        "android_base": "AOSP 17",
        "kernel_version": KERNEL_VERSION,
        "selected_display": "pinned Qualcomm WAIPIO SDE/DSI",
        "selected_xiaomi_mi_disp_present": False,
        "qualcomm_sde_dsi_dsc_source_present": True,
        "mondrian_udfps_lhbm_qualified": False,
        "mondrian_m11a_or_r66451_panel_qualified": False,
        "production_display_allowed": False,
        "physical_device_verified": False,
        "status": "BLOCKED_MISSING_MONDRIAN_XIAOMI_LHBM_ABI_AND_FACTORY_PANEL",
    }


def audit(kernel, reference):
    sha = verify_oem_reference(reference)
    report = inspect_mondrian_kernel(kernel)
    report["oem_reference"] = {
        "repository": OEM_REFERENCE_REPO,
        "branch": OEM_REFERENCE_BRANCH,
        "commit": sha,
        "source_from_other_xiaomi_device": True,
        "read_only_comparison": True,
        "source_imported_to_mondrian": False,
        "verified_git_blob_count": len(OEM_BLOBS),
    }
    report["lineage_code_imported"] = False
    report["open_qualification"] = [
        "factory mondrian panel/SKU/DSC/ESD and local HBM command verification",
        "native Xiaomi display ABI implemented against pinned Qualcomm MSM DRM",
        "AOSP17 UDFPS HAL, compositor, VINTF and SELinux integration",
        "physical Goodix fingerprint, LHBM and panel suspend/resume tests",
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, default=Path("."))
    parser.add_argument("--xiaomi-reference", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = audit(args.kernel.resolve(), args.xiaomi_reference.resolve())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\\n")
    except (OSError, SourceAuditError) as exc:
        parser.error(str(exc))
    print("[PASS] Xiaomi-published display/LHBM source reference pinned")
    print("[PASS] Qualcomm MSM/DSI source remains exact and Xiaomi DRM unmodified")
    print("[BLOCKED] no qualified mondrian LHBM/UDFPS ABI or factory panel; "
          "DO NOT enable this in an AOSP 17 product")


if __name__ == "__main__":
    main()
