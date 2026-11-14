#!/usr/bin/env python3
"""Verify a pinned Qualcomm WAIPIO driver without activating a conflicting DRM.

This is a source/layout validation, not a successful msm_drm.ko compile
or Android 17 HWC / panel compatibility certificate.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = ROOT / "techpack/display"
EXPECTED_BLOBS = {
    "Kbuild": "cd50990e1abfbbbf37862c1fb5b231c1cc07571b",
    "config/gki_waipiodisp.conf": "6822eb3116a5b220ca3ce8850c28ab35f0e6eb52",
    "msm/Kbuild": "ec664f1b1b5c575a76981e3df1b010c95399cdd4",
    "msm/sde_dbg.h": "ab9b3f69e6b8c78006347c78645260307d25c342",
    "msm/qcom_display_internal.h": "574d1c903e6c04edfc247f76dd829c25f92c5e66",
    "msm/sde_hdcp_2x.c": "9a497ce0370a33a02822cff6ec06e33cc209c9ca",
    "msm/dp/dp_panel.h": "64d287309a78ac09d8e2eeccfcc484448c40f187",
    "msm/dp/dp_mst_sim.c": "9f8c1351862a4eaf540a7f7061ef779ca820c21b",
    "msm/hfi/hfi_defs_common.h": "13075ad5baf29c8ee6a85c6029f289111c2ba60d",
    "msm/sde/sde_hw_catalog.c": "2e1adf37b30a2e0645f43ffafac3c363e947c517",
    "msm/sde/sde_hw_reg_dma_v1.c": "d1d7d344ff1a7470a9373f22b09c780e75496b3a",
    "msm/dsi/dsi_panel.c": "3a355e554740a78efbd0b15f886abfee006ad9a7",
    "msm/dsi/dsi_drm.c": "3c52f593cbae74edb64f65cadece113f5b8825e8",
    "msm/dsi/dsi_display.c": "30834f3f1cdc7e64fc4d1273837c96d8f6286537",
}
OEM_GENERIC_MAKEFILE_SHA = "340682cd0f320d83921799eaff3f716c7e08fc1a"

def check(ok, reason):
    if not ok:
        raise RuntimeError(reason)

def hash_blob(content):
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + bytes([0]) + content
    ).hexdigest()

def verify_build_profiles():
    """Evaluate the real Kbuild: ARCH_QCOM must not override OEM WAIPIO."""
    for name, waipio, vm, config, header in (
        ("WAIPIO", "y", "n", "gki_waipiodisp.conf", "gki_waipiodispconf.h"),
        ("WAIPIO TUI", "y", "y", "gki_waipiodisptui.conf", "gki_waipiodisptuiconf.h"),
        ("generic QCOM", "n", "n", "qcomdisp.mk", "qcomdispconf.h"),
    ):
        expected = dict(re.findall(
            r"^(?:export\s+)?(CONFIG_\w+)\s*:?=\s*(\w+)\s*$",
            (DISPLAY / "config" / config).read_text(), re.MULTILINE))
        keys = sorted(set(expected) | {
            "CONFIG_MDSS_HFI", "CONFIG_DRM_MSM_HDMI", "LINUX_INC", "msm_drm-y"})
        script = (
            f"DISPLAY_ROOT := {DISPLAY}\n"
            "CONFIG_ARCH_QCOM := y\n"
            f"CONFIG_ARCH_WAIPIO := {waipio}\n"
            f"CONFIG_ARCH_CAPE := {waipio}\n"
            f"CONFIG_ARCH_QTI_VM := {vm}\n"
            "include $(DISPLAY_ROOT)/msm/Kbuild\n"
            + "".join(f"$(info PE_PROFILE:{key}=$({key}))\n" for key in keys)
            + ".PHONY: profile\nprofile: ; @:\n")
        result = subprocess.run(
            ["make", "-rR", "--no-print-directory", "-f", "-", "profile"],
            input=script, text=True, capture_output=True, check=True, cwd=ROOT)
        actual = dict(line.removeprefix("PE_PROFILE:").split("=", 1)
                      for line in result.stdout.splitlines()
                      if line.startswith("PE_PROFILE:"))
        check(all(actual.get(key) == value for key, value in expected.items()),
              f"{name}: Kbuild changed an official profile option")
        forced_headers = re.findall(r"-include\s+(\S+)", actual["LINUX_INC"])
        check(forced_headers == [str(DISPLAY / "config" / header)],
              f"{name}: conflicting forced configuration headers: {forced_headers}")
        selected_objects = actual["msm_drm-y"].split()
        check(len(selected_objects) == len(set(selected_objects)),
              f"{name}: duplicate object linked into msm_drm.o")
        objects = set(selected_objects)
        check({"sde/sde_hw_dsc.o", "sde/sde_hw_dsc_1_2.o", "sde_dsc_helper.o",
               "dsi/dsi_panel.o"} <= objects,
              f"{name}: native SDE/DSI/DSC objects were lost")
        if actual.get("CONFIG_DRM_MSM_DP") == "y":
            check("dp/dp_lttpr_compat.o" in objects,
                  f"{name}: real OEM 5.10 DP LTTPR AUX backport was not linked")
        else:
            check("dp/dp_lttpr_compat.o" not in objects,
                  f"{name}: DP compatibility object leaked into a DP-disabled profile")
        if waipio == "y":
            check(not actual["CONFIG_MDSS_HFI"] and not actual["CONFIG_DRM_MSM_HDMI"],
                  f"{name}: generic HDMI/HFI options leaked into the OEM profile")
    print("[PASS] evaluated WAIPIO/TUI and generic Kbuild profiles; native DSC retained")

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
    # Duplicate object references create repeated ELF definitions at ld -r.
    # Check all recipes, including the optional rotator recipe, not only WAIPIO.
    listed_objects = re.findall(r"(?:\.\./)?(?:[\w-]+/)*[\w-]+\.o\b", kbuild)
    duplicates = sorted({obj for obj in listed_objects
                         if listed_objects.count(obj) > 1})
    check(not duplicates, f"Display Kbuild duplicates ELF objects: {duplicates}")
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
    dp_lttpr = (DISPLAY / "msm/dp/dp_lttpr_compat.c").read_text()
    dp_panel = (DISPLAY / "msm/dp/dp_panel.c").read_text()
    dp_display = (DISPLAY / "msm/dp/dp_display.c").read_text()
    check("drm_dp_dpcd_read(aux," in dp_lttpr and
          "DP_LT_TUNABLE_PHY_REPEATER_FIELD_DATA_STRUCTURE_REV +" in dp_lttpr and
          "hweight8(count)" in dp_lttpr and
          "ret != block_size" in dp_lttpr,
          "LTTPR OEM 5.10 compatibility must perform real DPCD/AUX I/O")
    check("pe_waipio_dp_read_lttpr_common_caps(" in dp_panel and
          "pe_waipio_dp_lttpr_count(" in dp_display and
          "drm_dp_lttpr_count(" not in dp_display and
          "drm_dp_read_lttpr_common_caps(" not in dp_panel,
          "DP consumers must use the reviewed local Linux 5.10 implementation")
    for path in ("sde_hw_dspp.c", "sde_hw_sspp.c", "sde_hw_sspp_v1.c"):
        source = (DISPLAY / "msm/sde" / path).read_text()
        check("#if IS_ENABLED(CONFIG_MDSS_HFI)" in source,
              f"{path}: HFI-only color callback must not link in WAIPIO HWIO")
    # Preserve real HWIO REG DMA. The two remaining MODPOST undefined symbols
    # were referenced only by the optional HFI LUT DMA firmware transport.
    # Verify their call sites and HFI-only callback registration are guarded.
    reg_dma = (DISPLAY / "msm/sde/sde_hw_reg_dma_v1.c").read_text()
    check("ops.kick_off[MSM_DISP_OP_HWIO] = kick_off_v1" in reg_dma and
          "static int write_kick_off_v1(" in reg_dma,
          "OEM WAIPIO must retain the hardware REG DMA kickoff")
    hfi_blocks = []
    active = []
    for line in reg_dma.splitlines():
        stripped = line.strip()
        if re.match(r"#if(?:def|ndef)?\\b", stripped):
            active.append(stripped)
        elif re.match(r"#else\\b|#elif\\b", stripped):
            if active:
                active[-1] = "alternate: " + active[-1]
        elif re.match(r"#endif\\b", stripped):
            check(bool(active), "unbalanced HFI REG DMA preprocessor guards")
            active.pop()
        if re.search(r"\\bhfi_util_u32_prop_helper_add_prop(?:_by_obj)?\\s*\\(", line):
            hfi_blocks.append(line)
            check("#if IS_ENABLED(CONFIG_MDSS_HFI)" in active,
                  "HFI REG DMA references firmware helpers without CONFIG_MDSS_HFI")
        if "ops.kick_off[MSM_DISP_OP_HFI] = hfi_kick_off_v1" in line:
            check("#if IS_ENABLED(CONFIG_MDSS_HFI)" in active,
                  "HFI DMA callback registered in the non-HFI WAIPIO profile")
    check(not active, "unbalanced HFI REG DMA preprocessor guards")
    check(len(hfi_blocks) == 3,
          "unexpected HFI REG DMA color serialization call inventory")
    hdcp = (DISPLAY / "hdcp/msm_hdcp.c").read_text()
    check("void __init msm_hdcp_register(void)" in hdcp and
          "void __exit msm_hdcp_unregister(void)" in hdcp and
          "static void __init msm_hdcp_register" not in hdcp and
          "static void __exit msm_hdcp_unregister" not in hdcp,
          "real HDCP platform-driver entry points must be globally linkable")
    dsi_src = (DISPLAY / "msm/dsi/dsi_display.c").read_text()
    dsi_hfi_src = (DISPLAY / "msm/dsi/hfi/dsi_display_hfi.c").read_text()
    sde_kms = (DISPLAY / "msm/sde/sde_kms.c").read_text()
    check("static void dsi_display_setup_ops(" in dsi_src and
          "display->display_ops.display_prepare[MSM_DISP_OP_HWIO]" in dsi_src and
          "#if IS_ENABLED(CONFIG_MDSS_HFI)" in dsi_src and
          "void dsi_display_hfi_setup_ops(" in dsi_hfi_src,
          "standard DSI HWIO callbacks must not depend on optional HFI objects")
    check("#if IS_ENABLED(CONFIG_MDSS_HFI)\nstatic int sde_kms_setup_hfi(" in sde_kms and
          "#if IS_ENABLED(CONFIG_MDSS_HFI)\nstatic int _sde_kms_send_reg_dma_last_cmd_hfi(" in sde_kms,
          "optional SDE HFI initialization must not link into the non-HFI WAIPIO profile")
    check((DISPLAY / "LICENSE.txt").is_file() and
          (DISPLAY / "NOTICE").is_file(),
          "Qualcomm source license/NOTICE missing")
    check("7b546db38822a40bc1beb5a9ace006b6541b947f" in
          (DISPLAY / "PE_REBORN_SOURCE_PROVENANCE.md").read_text(),
          "Qualcomm source commit not attributed")
    check(not (ROOT / "techpack/mm-drivers").exists(),
          "unexpected unreviewed multimedia dependency imported")

    verify_build_profiles()

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
