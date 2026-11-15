#!/usr/bin/env python3
"""Read-only privacy-limited mondrian Xiaomi OEM kernel / Android17 boot census.

Requires an already booted user-owned device with adb authorization.
Never flashes, roots, remounts, changes properties or reads user data.
A successful collection NEVER certifies PE-Reborn or hardware readiness.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

PINNED = {
    "oem_kernel": "2466406b9beac724960b0c88e6e794421d0466e7",
    "qualcomm_display": "e264bdd6c99d09b56da12febc61b0bc0daf59f44",
    "modules": "95b795b6167bc83c1b3fa5d68f85b0906808c51c",
    "devicetrees": "a7c1a5cf190e345a02b59818e211fd4338e20ce1",
}
PROPS = (
    "ro.product.device", "ro.product.vendor.device", "ro.vendor.product.device",
    "ro.build.version.release", "ro.build.version.sdk", "ro.boot.hardware",
    "ro.boot.slot_suffix", "ro.build.type", "sys.boot_completed",
)
MOUNT_POINTS = frozenset(("/", "/system", "/vendor", "/product", "/odm",
                          "/system_ext", "/vendor_dlkm", "/metadata", "/data"))
MODULES = ("msm_drm", "msm_mmrm", "qca_cld3_qca6490", "icnss2", "cfg80211",
           "cnss_prealloc", "cnss_nl", "cnss_utils", "mi_cnss_statistic",
           "qti_cpufreq_cdev", "qti_devfreq_cdev", "goodix_brl", "goodix_ts")
SAFE_DSI = re.compile(r"^card[0-9]+-DSI-[0-9]+$")
SAFE_COOLING = re.compile(r"^cooling_device[0-9]{1,4}$")
SAFE_POLICY = re.compile(r"^policy[0-9]{1,3}$")
SAFE_MODULE = re.compile(r"^[a-z0-9_][a-z0-9_.+-]{0,95}$")
MAX_CAPTURE = 512 * 1024


class EvidenceError(RuntimeError):
    pass


class ReadOnlyADB:
    def __init__(self, adb="adb", serial=None, runner=subprocess.run):
        self.adb, self.serial, self.runner = adb, serial, runner

    def call(self, *args):
        argv = [self.adb]
        if self.serial:
            argv.extend(["-s", self.serial])
        argv.extend(args)
        try:
            proc = self.runner(argv, capture_output=True, check=False, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if proc.returncode != 0 or not isinstance(proc.stdout, bytes):
            return None
        return proc.stdout[:MAX_CAPTURE].decode("utf-8", "replace").strip()

    def prop(self, name):
        if name not in PROPS:
            raise ValueError("property not permitted")
        return self.call("shell", "getprop", name)

    def read(self, path):
        if path not in ("/proc/mounts", "/proc/modules",
                        "/proc/device-tree/compatible", "/proc/device-tree/model"):
            raise ValueError("path not permitted")
        return self.call("shell", "cat", path)

    def connector_status(self, name):
        if not SAFE_DSI.fullmatch(name):
            raise ValueError("connector not permitted")
        return self.call("shell", "cat", "/sys/class/drm/" + name + "/status")

    def thermal_attribute(self, device, attr):
        if not SAFE_COOLING.fullmatch(device) or attr not in (
                "type", "cur_state", "max_state"):
            raise ValueError("thermal sysfs path not permitted")
        return self.call("shell", "cat",
                         "/sys/class/thermal/" + device + "/" + attr)

    def cpufreq_attribute(self, policy, attr):
        if not SAFE_POLICY.fullmatch(policy) or attr not in (
                "scaling_cur_freq", "scaling_max_freq", "cpuinfo_max_freq"):
            raise ValueError("cpufreq sysfs path not permitted")
        return self.call("shell", "cat",
                         "/sys/devices/system/cpu/cpufreq/" + policy + "/" + attr)


def parse_mounts(text):
    entries = {}
    for line in (text or "").splitlines():
        words = line.split()
        if len(words) >= 3 and words[1] in MOUNT_POINTS:
            entries[words[1]] = words[2]
    return entries


def parse_modules(text):
    if text is None:
        return {"proc_modules_readable": False,
                "observed_relevant_modules": [],
                "requested_module_names_observed": {}}
    all_names = set()
    for line in text.splitlines():
        name = line.split(maxsplit=1)[0] if line.strip() else ""
        if SAFE_MODULE.fullmatch(name):
            all_names.add(name.lower().replace("-", "_"))
    return {
        "proc_modules_readable": True,
        "observed_relevant_modules": sorted(
            name for name in all_names
            if name in MODULES or "goodix" in name or "fingerprint" in name),
        # A built-in driver never appears in proc/modules, so absence is not
        # automatic module-load failure or a release decision.
        "requested_module_names_observed": {
            name: name in all_names for name in MODULES
        },
    }


def compatible_names(text):
    if text is None:
        return []
    parts = text.split("\x00")[:32]
    return [part for part in parts if len(part) < 128
            and re.fullmatch(r"[\w,._+-]+", part)
            and part.startswith(("qcom,", "xiaomi,"))]


def _bounded_number(value, cap=100000000):
    if value is None or not value.isascii() or not value.isdecimal():
        return None
    parsed = int(value)
    return parsed if parsed <= cap else None


def thermal_and_cpufreq(adb):
    cooling_devices = {}
    listing = adb.call("shell", "ls", "-1", "/sys/class/thermal")
    if listing:
        for name in sorted(
                [x for x in listing.splitlines() if SAFE_COOLING.fullmatch(x)],
                key=lambda x: int(x.removeprefix("cooling_device")))[:128]:
            cooling_type = adb.thermal_attribute(name, "type")
            # The Qualcomm OEM driver emits cpu%d; do not claim an actual
            # cooling device exists just because its module was compiled.
            if not cooling_type or len(cooling_type) > 80:
                continue
            cooling_devices[name] = {
                "type": cooling_type,
                "current_state": _bounded_number(
                    adb.thermal_attribute(name, "cur_state"), 100000),
                "max_state": _bounded_number(
                    adb.thermal_attribute(name, "max_state"), 100000),
            }
    policies = {}
    listing = adb.call("shell", "ls", "-1",
                       "/sys/devices/system/cpu/cpufreq")
    if listing:
        for policy in sorted(
                [x for x in listing.splitlines() if SAFE_POLICY.fullmatch(x)],
                key=lambda x: int(x.removeprefix("policy")))[:16]:
            policies[policy] = {
                "scaling_cur_freq_khz": _bounded_number(
                    adb.cpufreq_attribute(policy, "scaling_cur_freq")),
                "scaling_max_freq_khz": _bounded_number(
                    adb.cpufreq_attribute(policy, "scaling_max_freq")),
                "cpuinfo_max_freq_khz": _bounded_number(
                    adb.cpufreq_attribute(policy, "cpuinfo_max_freq")),
            }
    return {
        "thermal_cooling_devices": cooling_devices,
        "cpu_thermal_cdev_types_observed": sorted(
            {item["type"] for item in cooling_devices.values()
             if re.fullmatch(r"cpu[0-9]+", item["type"])}),
        "cpufreq_policies": policies,
        "qos_limits_and_real_thermal_behavior_verified": False,
    }


def collect(adb):
    if adb.call("get-state") != "device":
        raise EvidenceError("adb device not connected/authorized; no report produced")
    p = {key: adb.prop(key) for key in PROPS}
    is_mondrian = "mondrian" in (
        p["ro.product.device"], p["ro.product.vendor.device"],
        p["ro.vendor.product.device"])
    android17 = p["ro.build.version.release"] == "17"
    uname = adb.call("shell", "uname", "-r")
    linux51081 = bool(uname and re.match(r"^5\.10\.81(?:[.-]|$)", uname))
    boot_completed = p["sys.boot_completed"] == "1"
    enforce = adb.call("shell", "getenforce")
    if enforce not in ("Enforcing", "Permissive", "Disabled"):
        enforce = "unavailable"
    connectors = {}
    drm_ls = adb.call("shell", "ls", "-1", "/sys/class/drm")
    if drm_ls:
        for name in [x for x in drm_ls.splitlines()
                     if SAFE_DSI.fullmatch(x)][:8]:
            result = adb.connector_status(name)
            connectors[name] = result if result in (
                "connected", "disconnected", "unknown") else "unavailable"
    root_model = adb.read("/proc/device-tree/model")
    observations = {
        "device_props": {key: p[key] for key in PROPS if key.startswith("ro.product")
                         or key == "ro.vendor.product.device"},
        "device_codename_mondrian_observed": is_mondrian,
        "android_release": p["ro.build.version.release"],
        "android_sdk_reported": p["ro.build.version.sdk"],
        "android_17_observed": android17,
        "linux_release": uname,
        "original_oem_linux_5_10_81_observed": linux51081,
        "sys_boot_completed": boot_completed,
        "selinux_mode": enforce,
        "slot_suffix": p["ro.boot.slot_suffix"],
        "boot_hardware": p["ro.boot.hardware"],
        "build_type": p["ro.build.type"],
        "dt_model": root_model.replace("\x00", "")[:128] if root_model else None,
        "dt_compatible": compatible_names(
            adb.read("/proc/device-tree/compatible")),
        "mount_filesystems": parse_mounts(adb.read("/proc/mounts")),
        "kernel_modules": parse_modules(adb.read("/proc/modules")),
        "dsi_status": connectors,
        "thermal_and_cpufreq": thermal_and_cpufreq(adb),
    }
    return {
        "schema_version": 1,
        "scope": "mondrian OEM kernel 5.10.81 / PE-Reborn AOSP17",
        "source_pin_reference_not_verified_on_phone": PINNED,
        "utc": datetime.now(timezone.utc).isoformat(),
        "serial_imei_or_user_data_collected": False,
        "observations": observations,
        "target_boot_identity_observed": bool(
            is_mondrian and android17 and linux51081 and boot_completed),
        "qualification": {
            "PE_Reborn_ROM_identity_attested": False,
            "M11A_DSC_ESD_refresh_hardware_verified": False,
            "Goodix_UDFPS_LHBM_and_touch_verified": False,
            "WLAN_firmware_and_rf_verified": False,
            "thermal_suspend_resume_verified": False,
            "modules_vendor_dlkm_loadorder_verified": False,
            "boot_vendor_boot_dtbo_release_approved": False,
            "Android17_VINTF_GKI_FCM_VTS_verified": False,
            "full_kernel_hardware_release_approved": False,
        },
        "status": "DIAGNOSTIC_ONLY_NOT_HARDWARE_QUALIFIED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", help="adb selector; never recorded in report")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        evidence = collect(ReadOnlyADB(args.adb, args.serial))
    except EvidenceError as exc:
        parser.error(str(exc))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print("[COLLECTED] Read-only evidence: " + str(args.out))
    print("[BLOCKED] No ROM, hardware, GKI/FCM, LHBM, thermal or vendor_dlkm "
          "release qualification can be inferred.")


if __name__ == "__main__":
    main()
