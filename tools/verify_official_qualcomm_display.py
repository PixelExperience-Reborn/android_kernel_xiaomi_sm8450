#!/usr/bin/env python3
"""Verify a pinned Qualcomm WAIPIO driver without activating a conflicting DRM.

This is a source/layout validation, not a successful msm_drm.ko compile
or Android 17 HWC / panel compatibility certificate.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "techpack/display"
EXPECTED_BLOBS = {
    "Kbuild": "cd50990e1abfbbbf37862c1fb5b231c1cc07571b",
    "config/gki_waipiodisp.conf": "6822eb3116a5b220ca3ce8850c28ab35f0e6eb52",
    "msm/Kbuild": "26744bed61323b4bd7267b11da6577867ff58c65",
    "msm/sde_dbg.h": "ab9b3f69e6b8c78006347c78645260307d25c342",
    "msm/qcom_display_internal.h": "574d1c903e6c04edfc247f76dd829c25f92c5e66",
    "msm/sde_hdcp_2x.c": "9a497ce0370a33a02822cff6ec06e33cc209c9ca",
    "msm/dp/dp_panel.h": "64d287309a78ac09d8e2eeccfcc484448c40f187",
    "msm/dp/dp_mst_sim.c": "9f8c1351862a4eaf540a7f7061ef779ca820c21b",
    "msm/hfi/hfi_defs_common.h": "13075ad5baf29c8ee6a85c6029f289111c2ba60d",
    "msm/sde/sde_hw_catalog.c": "2e1adf37b30a2e0645f43ffafac3c363e947c517",
    "msm/dsi/dsi_panel.c": "3a355e554740a78efbd0b15f886abfee006ad9a7",
}
OEM_GENERIC_MAKEFILE_SHA = "340682cd0f320d83921799eaff3f716c7e08fc1a"

def check(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def hash_blob(content):
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + bytes([0]) + content
    ).hexdigest()

def main():
    tracked = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z", "--", "techpack/display"]
    ).split(b"\0")
    imported_count = len([path for path in tracked if path])
    check(imported_count >= 500,
          f"partial Qualcomm display snapshot: {imported_count} paths")
    for relative, digest in EXPECTED_BLOBS.items():
        item = DISPLAY / relative
        check(item.is_file(), f"missing Qualcomm driver source: {relative}")
        check(hash_blob(item.read_bytes()) == digest,
              f"unreviewed Qualcomm driver change: {relative}")

    # Verified compatibility adjustments in this isolated Qualcomm trial:
    # Clang 23 has no GCC-only maybe-uninitialized suppression option;
    # OEM Linux 5.10 provides <stdarg.h> rather than <linux/stdarg.h>.
    check("-Wno-maybe-uninitialized" not in
          (DISPLAY / "msm/Kbuild").read_text(),
          "GCC-only display warning flag must not reach Android LLVM23")
    check("#include <stdarg.h>" in
          (DISPLAY / "msm/sde_dbg.h").read_text(),
          "SDE must use the Linux 5.10 compatible variadic header")

    compat = (DISPLAY / "msm/qcom_display_internal.h").read_text()
    check("#include <linux/soc/qcom/msm_mmrm.h>" in compat and
          "#include <linux/qcom-iommu-util.h>" in compat,
          "Display must use the actual OEM MMRM and IOMMU declarations")
    check("#include <linux/qcom_scm.h>" in compat and
          "static inline int qcom_scm_mem_protect_sd_ctrl(" not in compat,
          "SDE secure memory must use real OEM SCM, never a fake success stub")
    check(all(x in compat for x in (
          "#include <linux/soc/qcom/panel_event_notifier.h>",
          "#include <linux/soc/qcom/altmode-glink.h>",
          "#include <linux/ipc_logging.h>")),
          "Panel, Type-C altmode and IPC logging must use real OEM APIs")
    check("static inline void *panel_event_notifier_register(" not in compat and
          "static inline void *ipc_log_context_destroy(" not in compat,
          "Upstream no-op panel/logging callbacks are forbidden")
    check("#include <soc/qcom/of_common.h>" in compat and
          "static inline int of_fdt_get_ddrtype(" not in compat,
          "Display DDR type must come from the real OEM OF API")
    dp = (DISPLAY / "msm/dp/dp_panel.h").read_text()
    check("#define DP_LTTPR_COMMON_CAP_SIZE 8" in dp and
          "DP_LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV" in dp and
          "DP_PHY_REPEATER_CNT" in dp,
          "LTTPR capability buffer must use verified upstream size and OEM DPCD registers")
    check("enum mmrm_cb_type {" not in compat and
          "enum sid_switch_direction {" not in compat,
          "Display must not redeclare kernel MMRM/IOMMU enums")
    hfi = (DISPLAY / "msm/hfi/hfi_defs_common.h").read_text()
    check("#ifndef __KERNEL__" in hfi and
          "#endif /* !__KERNEL__ */" in hfi,
          "HFI userspace aliases must be isolated from Linux kernel types")

    original = ROOT / "drivers/gpu/drm/msm/Makefile"
    check(hash_blob(original.read_bytes()) == OEM_GENERIC_MAKEFILE_SHA,
          "original Xiaomi generic DRM sources were modified")
    panel_src = (DISPLAY / "msm/dsi/dsi_panel.c").read_text()
    qcom_cfg = (DISPLAY / "config/gki_waipiodisp.conf").read_text()
    kbuild = (DISPLAY / "msm/Kbuild").read_text()
    arch = (ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config").read_text()
    gki = (ROOT / "arch/arm64/configs/gki_defconfig").read_text()

    check("CONFIG_ARCH_WAIPIO=y" in arch and "CONFIG_ARCH_CAPE=y" in arch,
          "Qualcomm WAIPIO/CAPE board not selected")
    check("CONFIG_DRM=y" in gki, "DRM framework not configured")
    check("CONFIG_DRM_MSM=" not in arch + "\n" + gki,
          "unqualified in-tree DRM already selected; duplicate DRM risk")
    check("CONFIG_DISPLAY_BUILD=m" in qcom_cfg,
          "official WAIPIO DRM module recipe missing")
    check("ifeq ($(CONFIG_ARCH_WAIPIO), y)" in kbuild,
          "Qualcomm WAIPIO build integration missing")
    check("obj-m += msm_drm.o" in kbuild,
          "Qualcomm SDE not configured for external module build")
    check("dsi_panel_parse" in panel_src,
          "Qualcomm DSI panel parsing not found")
    check((DISPLAY / "LICENSE.txt").is_file() and
          (DISPLAY / "NOTICE").is_file(),
          "Qualcomm source license/NOTICE missing")
    check("7b546db38822a40bc1beb5a9ace006b6541b947f" in
          (DISPLAY / "PE_REBORN_SOURCE_PROVENANCE.md").read_text(),
          "Qualcomm source commit not attributed")
    check(not (ROOT / "techpack/mm-drivers").exists(),
          "unexpected unreviewed multimedia dependency imported")

    print(f"[PASS] {imported_count} official Qualcomm display-source paths")
    print("[PASS] WAIPIO SDE/DSI source pinned with reviewed Linux 5.10/LLVM23 adjustments")
    print("[PASS] original Xiaomi generic DRM unchanged and not selected")
    print("[BLOCKED] new Qualcomm msm_drm.ko needs Linux 5.10 KAPI/KMI "
          "and multimedia-header compatibility verification")
    print("[BLOCKED] Xiaomi M11A DSI panel, firmware and AOSP17 HWC "
          "must be qualified separately; no code was enabled in release")

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
