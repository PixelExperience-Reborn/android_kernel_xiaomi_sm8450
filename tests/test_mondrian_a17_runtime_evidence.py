"""Synthetic read-only ADB tests; never imply that a phone was booted."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from collect_mondrian_a17_runtime import (  # noqa: E402
    EvidenceError, ReadOnlyADB, collect, compatible_names,
    parse_modules, parse_mounts,
)

GETPROPS = {
    "ro.product.device": "mondrian",
    "ro.product.vendor.device": "mondrian",
    "ro.vendor.product.device": "mondrian",
    "ro.build.version.release": "17",
    "ro.build.version.sdk": "37",
    "ro.boot.hardware": "taro",
    "ro.boot.slot_suffix": "_a",
    "ro.build.type": "userdebug",
    "sys.boot_completed": "1",
}


class FakeADBRunner:
    def __init__(self, *, props=None, online=True):
        self.props = GETPROPS.copy() if props is None else props
        self.online = online
        self.calls = []

    def __call__(self, argv, *, capture_output, check, timeout):
        self.calls.append(tuple(argv))
        args = list(argv)
        self_assert = args.pop(0)
        if self_assert != "adb":
            raise AssertionError("expected adb executable")
        if args[:2] == ["-s", "test-serial-never-reported"]:
            args = args[2:]
        cmd = tuple(args)
        if cmd == ("get-state",):
            output = b"device\n" if self.online else b"unauthorized\n"
        elif cmd[:3] == ("shell", "getprop", cmd[2] if len(cmd) > 2 else ""):
            output = (self.props.get(cmd[2], "") + "\n").encode()
        elif cmd == ("shell", "uname", "-r"):
            output = b"5.10.81-gki\n"
        elif cmd == ("shell", "getenforce"):
            output = b"Enforcing\n"
        elif cmd == ("shell", "ls", "-1", "/sys/class/drm"):
            output = b"card0\ncard0-DSI-1\nrenderD128\n"
        elif cmd == ("shell", "cat", "/sys/class/drm/card0-DSI-1/status"):
            output = b"connected\n"
        elif cmd == ("shell", "cat", "/proc/modules"):
            output = b"msm_drm 1234 0 - Live 0x0\nmsm_mmrm 100 1 - Live 0x0\n"
        elif cmd == ("shell", "cat", "/proc/mounts"):
            output = (b"/dev/dm-0 /system erofs ro 0 0\n"
                      b"/dev/dm-1 /vendor erofs ro 0 0\n"
                      b"/dev/block/by-name/userdata /data f2fs rw 0 0\n"
                      b"/dev/block/by-name/metadata /metadata ext4 rw 0 0\n")
        elif cmd == ("shell", "cat", "/proc/device-tree/compatible"):
            output = b"qcom,cape-mtp\x00qcom,cape\x00unrelated\x00"
        elif cmd == ("shell", "cat", "/proc/device-tree/model"):
            output = b"Xiaomi mondrian\x00"
        else:
            raise AssertionError("unexpected command: " + repr(cmd))
        return subprocess.CompletedProcess(
            argv, 0, stdout=output, stderr=b"")


class MondrianADBContractTests(unittest.TestCase):
    def test_target_boot_observations_never_approve_hardware(self):
        runner = FakeADBRunner()
        adb = ReadOnlyADB(serial="test-serial-never-reported", runner=runner)
        data = collect(adb)
        self.assertTrue(data["target_boot_identity_observed"])
        self.assertTrue(data["observations"]["android_17_observed"])
        self.assertEqual(data["observations"]["linux_release"], "5.10.81-gki")
        self.assertEqual(data["observations"]["selinux_mode"], "Enforcing")
        self.assertEqual(data["observations"]["mount_filesystems"]["/system"], "erofs")
        self.assertEqual(data["observations"]["mount_filesystems"]["/data"], "f2fs")
        self.assertTrue(data["observations"]["kernel_modules"][
            "requested_module_names_observed"]["msm_drm"])
        self.assertEqual(data["observations"]["dsi_status"]["card0-DSI-1"],
                         "connected")
        self.assertTrue(data["serial_imei_or_user_data_collected"] is False)
        for qualified in data["qualification"].values():
            self.assertFalse(qualified)
        self.assertNotIn("test-serial-never-reported", json.dumps(data))
        for argv in runner.calls:
            self.assertIn(argv[3], ("get-state", "shell"))
            self.assertNotIn("root", argv)
            self.assertNotIn("push", argv)
            self.assertNotIn("remount", argv)
            self.assertNotIn("flash", argv)

    def test_wrong_device_cannot_be_marked_as_mondrian(self):
        props = GETPROPS.copy()
        props["ro.product.device"] = "ziyi"
        props["ro.product.vendor.device"] = "ziyi"
        props["ro.vendor.product.device"] = "ziyi"
        record = collect(ReadOnlyADB(runner=FakeADBRunner(props=props)))
        self.assertFalse(record["observations"]["device_codename_mondrian_observed"])
        self.assertFalse(record["target_boot_identity_observed"])

    def test_wrong_android_release_cannot_be_accepted(self):
        props = GETPROPS.copy()
        props["ro.build.version.release"] = "16"
        record = collect(ReadOnlyADB(runner=FakeADBRunner(props=props)))
        self.assertFalse(record["target_boot_identity_observed"])

    def test_reject_unauthorized_adb_state(self):
        with self.assertRaises(EvidenceError):
            collect(ReadOnlyADB(runner=FakeADBRunner(online=False)))

    def test_only_preapproved_properties_are_read(self):
        with self.assertRaises(ValueError):
            ReadOnlyADB(runner=FakeADBRunner()).prop("ro.serialno")

    def test_allowlisted_sysfs_dsi_paths_cannot_be_traversed(self):
        with self.assertRaises(ValueError):
            ReadOnlyADB(runner=FakeADBRunner()).connector_status("../foo")
        with self.assertRaises(ValueError):
            ReadOnlyADB(runner=FakeADBRunner()).read("/data/system/users/0.xml")

    def test_missing_proc_modules_means_not_observed_not_failed(self):
        self.assertFalse(parse_modules(None)["proc_modules_readable"])
        self.assertEqual(parse_modules(None)["requested_module_names_observed"], {})

    def test_module_names_are_normalized_and_unrelated_are_omitted(self):
        report = parse_modules(
            "msm-drm 12 0 - Live 0x0\n"
            "qca_cld3_qca6490 123 0 - Live 0x0\n"
            "private-name 50 0 - Live 0x0\n")
        self.assertEqual(report["observed_relevant_modules"],
                         ["msm_drm", "qca_cld3_qca6490"])
        self.assertNotIn("private-name", json.dumps(report))

    def test_whitelisted_mountpoint_filesystems_only(self):
        out = parse_mounts("/dev/a /system erofs ro 0 0\n"
                           "/dev/private /data/media/0 ext4 rw 0 0\n")
        self.assertEqual(out, {"/system": "erofs"})

    def test_binary_device_tree_compatible_does_not_dump_other_data(self):
        self.assertEqual(
            compatible_names("qcom,cape\x00device,private\x00xiaomi,m11a\x00"),
            ["qcom,cape", "xiaomi,m11a"])


if __name__ == "__main__":
    unittest.main()
