#!/usr/bin/env python3
"""Safeguard the OEM Qualcomm WAIPIO/CAPE display clock while bringing up mondrian.

Source-level requirements only; a compile and physical device test are separate.
Do not copy another ROM's display controller or replace Qualcomm CAPE PLL values.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def check(value, message):
    if not value:
        raise ValueError(message)


def main():
    clock = (ROOT / "drivers/clk/qcom/dispcc-waipio.c").read_text()
    make = (ROOT / "drivers/clk/qcom/Makefile").read_text()
    board = (ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config").read_text()
    header = (ROOT / "include/linux/pm_runtime.h").read_text()
    gki = (ROOT / "arch/arm64/configs/gki_defconfig").read_text()
    kms = (ROOT / "drivers/gpu/drm/msm/Kconfig").read_text()
    generic = (ROOT / "drivers/gpu/drm/msm/Makefile").read_text()
    techpack = (ROOT / "techpack/Kbuild").read_text()

    check('compatible = "qcom,cape-dispcc"' in clock,
          "Xiaomi CAPE/SM8475 DISPCC compatible lost")
    check('compatible = "qcom,waipio-dispcc"' in clock,
          "Qualcomm WAIPIO DISPCC fallback lost")
    check('if (!strcmp(compat, "qcom,cape-dispcc"))' in clock
          and "disp_cc_cape_fixup(regmap);" in clock,
          "CAPE-specific PLL fixup no longer selected")
    for tag in ("disp_cc_pll0_cape_init", "disp_cc_pll1_cape_init",
                "CLK_ALPHA_PLL_TYPE_LUCID_OLE"):
        check(tag in clock, f"CAPE display clock setup incomplete: {tag}")
    check("CONFIG_MSM_DISPCC_WAIPIO=m" in board,
          "mondrian display clock kernel module no longer selected")
    check("CONFIG_MSM_EXT_DISPLAY=m" in board,
          "original Qualcomm external display glue no longer selected")
    check("obj-$(CONFIG_MSM_DISPCC_WAIPIO) += dispcc-waipio.o" in make,
          "Qualcomm display clock Kbuild disconnected")
    # The *original* OEM Linux headers include this newer PM API.
    check("pm_runtime_resume_and_get(struct device *dev)" in header,
          "this OEM kernel does not implement checked runtime PM API")
    probe = clock.split("static int disp_cc_waipio_probe(", 1)[1].split(
        "static void disp_cc_waipio_sync_state(", 1
    )[0]
    check("pm_runtime_resume_and_get(&pdev->dev)" in probe,
          "display clock probe still interprets positive PM success as error")
    check("pm_runtime_get_sync(&pdev->dev)" not in probe,
          "unsafe legacy PM get used by display clock probe")
    check("if (ret)\n\t\tgoto err_pm_put;" in probe,
          "CAPE PLL fixup failures leak runtime PM reference")
    check("Failed to register DISP CC clocks" in probe and
          "goto err_pm_put;" in probe.split("Failed to register DISP CC clocks", 1)[1],
          "clock registration error lacks PM cleanup")
    check("err_pm_put:\n\tpm_runtime_put_sync(&pdev->dev);\n\treturn ret;" in probe,
          "runtime PM reference not balanced in error path")
    check("msm-y :=" in generic and "config DRM_MSM" in kms,
          "existing upstream MSM DRM infrastructure unexpectedly removed")
    # Actual user-facing display implementation on CAPE is the separate
    # Qualcomm msm_drm.ko; never duplicate it with the generic in-tree MSM.
    check("CONFIG_DRM_MSM=" not in board and "CONFIG_DRM_MSM=" not in gki,
          "potential conflicting in-kernel MSM DRM enabled")
    check(not (ROOT / "techpack/display").exists(),
          "unreviewed Qualcomm external display sources copied into OEM kernel")
    check("stub/" in techpack, "unexpected OEM techpack structure")
    print("[PASS] Original Qualcomm CAPE DISPCC preserved; PM success/error paths balanced")
    print("[PASS] No conflicting in-tree DRM_MSM or unreviewed external techpack import")
    print("[NOT VERIFIED] Qualcomm msm_drm.ko, M11A panel firmware, full KMI or physical boot")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, IndexError) as exc:
        print("[FAIL] " + str(exc), file=sys.stderr)
        sys.exit(1)
