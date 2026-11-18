#!/usr/bin/env python3
"""Verify the REAL compiled Xiaomi WL2866D module against the selected OEM kernel.

Use the Kbuild kernelrelease, not bare Linux VERSION.PATCHLEVEL.SUBLEVEL:
mondrian_GKI.config sets CONFIG_LOCALVERSION="-gki". Confirm exports from
the generated Module.symvers AND the actual ARM64 ELF. No hardware claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

REQUIRED_EXPORTS = (
    "wl2866d_camera_power_up",
    "wl2866d_camera_power_down",
    "wl2866d_camera_power_up_all",
    "wl2866d_camera_power_up_eeprom",
    "wl2866d_camera_power_down_eeprom",
)
OEM_RELEASE = re.compile(r"5[.]10[.]81(?:[-+][A-Za-z0-9._+\-]+)?")


def check_release(kernelrelease, vermagic):
    if not OEM_RELEASE.fullmatch(kernelrelease):
        raise ValueError("unexpected OEM kernelrelease (must be Linux 5.10.81): "
                         + repr(kernelrelease))
    tokens = vermagic.split()
    if not tokens or tokens[0] != kernelrelease:
        raise ValueError("WL2866D vermagic mismatch: "
                         + repr(vermagic) + " versus " + repr(kernelrelease))


def check_abi(symvers, nm):
    exports = set()
    for line in symvers.splitlines():
        cols = line.split()
        if (len(cols) >= 4 and cols[3].startswith("EXPORT_SYMBOL")
                and cols[2].split("/")[-1] == "wl2866d"):
            exports.add(cols[1])
    definitions = set()
    for line in nm.splitlines():
        cols = line.split()
        if len(cols) >= 2 and cols[1] in ("T", "W"):
            definitions.add(cols[0])
    for symbol in REQUIRED_EXPORTS:
        if symbol not in exports:
            raise ValueError("missing OEM WL2866D Module.symvers export: " + symbol)
        if symbol not in definitions:
            raise ValueError("missing actual OEM WL2866D ELF definition: " + symbol)
    return list(REQUIRED_EXPORTS)


def cmd(*args):
    return subprocess.check_output(list(map(str, args)), text=True).strip()


def verify(kernel, out, module, expected_kernel_commit):
    if not re.fullmatch("[0-9a-f]{40}", expected_kernel_commit):
        raise ValueError("expected exact Git kernel SHA")
    revision = cmd("git", "-C", kernel, "rev-parse", "HEAD")
    if revision != expected_kernel_commit:
        raise ValueError("kernel checkout drift: " + revision)
    for path in (module, out / "Module.symvers", out / ".config",
                 out / "vmlinux"):
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("compiled kernel/ELF evidence missing: " + str(path))
    config = (out / ".config").read_text()
    for option in ("CONFIG_LDO_WL2866D=m", "CONFIG_WL2866D=y"):
        if option not in config.splitlines():
            raise ValueError("wrong OEM Camera power config: " + option)
    name = cmd("modinfo", "-F", "name", module)
    if name != "wl2866d":
        raise ValueError("unexpected compiled Camera power module: " + name)
    release = cmd("make", "-s", "-C", kernel, f"O={out}", "kernelrelease")
    vermagic = cmd("modinfo", "-F", "vermagic", module)
    check_release(release, vermagic)
    if "AArch64" not in cmd("readelf", "-h", module):
        raise ValueError("WL2866D module is not ARM64")
    exported = check_abi((out / "Module.symvers").read_text(),
                         cmd("nm", "-P", module))
    return {
        "device": "mondrian",
        "kernel_commit": revision,
        "kernelrelease": release,
        "module_vermagic": vermagic,
        "module_name": name,
        "module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "exported_oem_power_functions": exported,
        "source_and_compiled_abi_verified": True,
        "camera_rails_hardware_verified": False,
        "camera_and_audio_product_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--kernel-out", required=True, type=Path)
    parser.add_argument("--module", required=True, type=Path)
    parser.add_argument("--expected-kernel-commit", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.kernel.resolve(), args.kernel_out.resolve(),
                        args.module.resolve(), args.expected_kernel_commit)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.error("compiled Xiaomi WL2866D ABI failed: " + str(error))
    print("[PASS] compiled Xiaomi WL2866D exports all five Camera power"
          " functions with exact OEM Kbuild kernelrelease/vermagic")
    print("[PENDING] hardware sensor power and runtime checks")


if __name__ == "__main__":
    main()
