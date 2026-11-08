#!/usr/bin/env python3
"""Check that PE-Reborn's mondrian branch contains actual, unmodified kernel sources.

This is a source-provenance and device scope test, not kernel compilation.
The original Linux/GPL headers and Qualcomm/Xiaomi downstream fixes remain
the authoritative source of licensing and hardware requirements.
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTED = "e1d05dc9f1cecd67b6e11bd25fb87b80947577fc"
CRITICAL_GIT_BLOBS = {
    "Makefile": "ac6ebd447d9518391afa8bd91587fed042f7cec4",
    "COPYING": "a635a38ef9405fdfcfe97f3a435393c1e9cae971",
    "build.config.msm.waipio": "82e031fe63b1cbb7d05c6933c406db3a67fd4738",
    "arch/arm64/configs/vendor/mondrian_GKI.config": "0eab40c4e8dfc69ed7ddcf2f9e45da24a1d9e182",
    "drivers/input/touchscreen/goodix_berlin_driver/goodix_brl_spi.c":
        "90ac0a60b3f4ae834a65c25c187b5b48b75d4b1e",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, check=True, text=True
    ).stdout.strip()


def git_blob_hash(content: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + bytes([0]) + content
    ).hexdigest()


def main() -> None:
    require(git("merge-base", "--is-ancestor", IMPORTED, "HEAD") == "",
            "source import commit is not an ancestor")
    total = len(git("ls-files", "-z").split(chr(0)))
    # trailing empty token after final NUL
    total -= 1
    require(total >= 68000, f"expected full kernel tree; found only {total} tracked paths")
    for file, expected in CRITICAL_GIT_BLOBS.items():
        data = (ROOT / file).read_bytes()
        require(git_blob_hash(data) == expected, f"upstream Git blob changed: {file}")
        print(f"[PASS] {file}: matches immutable upstream Git blob")
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    require("VERSION = 5" in make and "PATCHLEVEL = 10" in make and
            "SUBLEVEL = 269" in make, "unexpected kernel release")
    conf = (ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config").read_text()
    require("CONFIG_EROFS_FS=y" in conf, "mondrian EROFS kernel config missing")
    require("CONFIG_MI_CHARGER_M81=y" in conf, "mondrian charging driver not preserved")
    link = ROOT / "arch/arm64/boot/dts/vendor"
    require(link.is_symlink(), "external Qualcomm DT directory is not a symlink")
    require(link.readlink().as_posix() == "../../../../../sm8450-devicetrees",
            "external Qualcomm DT symlink points at the wrong repository")
    provenance = (ROOT / "docs/MONDRIAN_SOURCE_PROVENANCE.md").read_text()
    require("LF52406/android_kernel_xiaomi_sm8450" in provenance,
            "kernel source origin missing")
    require("MiCode/Xiaomi_Kernel_OpenSource" in provenance,
            "Xiaomi OEM partial-source reference missing")
    require((ROOT / "drivers").is_dir() and (ROOT / "arch/arm64").is_dir()
            and (ROOT / "fs").is_dir(), "real Linux source directories missing")
    print(f"[PASS] PE-Reborn kernel source contains {total} tracked files")
    print("[NOTE] source-only pass; not proof of build, KMI, DTBO, vendor or device boot")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
