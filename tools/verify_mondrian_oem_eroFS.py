#!/usr/bin/env python3
"""Fail-closed source/real Kconfig check for OEM-first AOSP17 mondrian.

Does not build a kernel binary, device-tree image, Qualcomm modules, Android
boot/vendor_boot images or prove KeyMint/SELinux firmware compatibility.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OEM_DEVICE_CONFIG = ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config"
GKI_BASE = ROOT / "arch/arm64/configs/gki_defconfig"
EROFS_KCONFIG = ROOT / "fs/erofs/Kconfig"

MANDATORY = {
    "CONFIG_EROFS_FS": "y",
    "CONFIG_EROFS_FS_XATTR": "y",
    "CONFIG_EROFS_FS_POSIX_ACL": "y",
    "CONFIG_EROFS_FS_SECURITY": "y",
    "CONFIG_EROFS_FS_ZIP": "y",
    "CONFIG_F2FS_FS": "y",
    "CONFIG_F2FS_FS_SECURITY": "y",
    "CONFIG_FS_ENCRYPTION": "y",
    "CONFIG_FS_ENCRYPTION_INLINE_CRYPT": "y",
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def settings(source):
    result = {}
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("CONFIG_") and "=" in stripped:
            key, value = stripped.split("=", 1)
            require(key not in result, f"duplicate Kconfig assignment: {key}")
            result[key] = value.strip()
    return result


def validate(actual=None):
    original = GKI_BASE.read_text(encoding="utf-8")
    fragment = OEM_DEVICE_CONFIG.read_text(encoding="utf-8")
    erofs_kconfig = EROFS_KCONFIG.read_text(encoding="utf-8")
    require("CONFIG_EROFS_FS=y" in original and "CONFIG_F2FS_FS=y" in original,
            "official Xiaomi GKI baseline lacks built-in EROFS/F2FS")
    # Xiaomi's published tree contains a Kconfig hard dependency on HWID,
    # but omitted the actual source directory. Require the minimal restored
    # M11A-capable implementation, not a commented-out Kconfig source line.
    misc_kconfig = (ROOT / "drivers/misc/Kconfig").read_text(encoding="utf-8")
    require('source "drivers/misc/hwid/Kconfig"' in misc_kconfig,
            "OEM Kconfig HWID requirement was removed instead of implemented")
    for p in ("drivers/misc/hwid/Kconfig", "drivers/misc/hwid/Makefile",
              "drivers/misc/hwid/hwid.c", "drivers/misc/hwid/hwid.h"):
        require((ROOT / p).is_file(), f"missing OEM HWID source dependency: {p}")
    header = (ROOT / "drivers/misc/hwid/hwid.h").read_text(encoding="utf-8")
    require("HARDWARE_PROJECT_M11A       14" in header,
            "restored HWID driver does not define mondrian M11A")
    keys = settings(fragment)
    for name, value in MANDATORY.items():
        require(keys.get(name) == value,
                f"mondrian fragment must explicitly require {name}={value}")
    for symbol in ("EROFS_FS", "EROFS_FS_XATTR", "EROFS_FS_POSIX_ACL",
                   "EROFS_FS_SECURITY", "EROFS_FS_ZIP"):
        require(f"config {symbol}" in erofs_kconfig,
                f"OEM kernel source lacks real Kconfig implementation: {symbol}")
    require("select LZ4_DECOMPRESS" in erofs_kconfig,
            "cannot assume AOSP EROFS/LZ4 images are readable")
    require("# CONFIG_EROFS_FS_DEBUG is not set" in fragment
            or "CONFIG_EROFS_FS_DEBUG=y" not in fragment,
            "production cannot force EROFS debug mode")
    if actual is not None:
        config = settings(actual.read_text(encoding="utf-8"))
        for name, value in MANDATORY.items():
            require(config.get(name) == value,
                    f"after olddefconfig, {name}={value} not accepted by OEM kernel")
        require(config.get("CONFIG_EROFS_FS_DEBUG") != "y",
                "shipping EROFS debug enabled")
        print("[PASS] OEM Kconfig processed nine EROFS/SELinux/F2FS/FBE requirements")
    else:
        print("[PASS] OEM source has EROFS/F2FS Kconfig and explicit mondrian flags")
    print("[NOTE] No device boot, FBE key verification, kernel build or partition image is implied")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--generated-config", type=Path)
    args = ap.parse_args()
    validate(args.generated_config)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
