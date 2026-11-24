"""Test actual Kbuild-version semantics and fail-closed OEM WL2866D ABI."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "wl2866d_abi", ROOT / "tools/verify_mondrian_wl2866d_abi.py"
)
abi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(abi)


def fixture(module="drivers/misc/wl2866d"):
    symvers = "\n".join(
        f"0xaabbccdd\t{s}\t{module}\tEXPORT_SYMBOL" for s in abi.REQUIRED_EXPORTS
    ) + "\n"
    nm = "\n".join(f"{s} T 00000000 10" for s in abi.REQUIRED_EXPORTS) + "\n"
    return symvers, nm


class MondrianWL2866DABITests(unittest.TestCase):
    def test_actual_gki_kernelrelease_supported(self):
        abi.check_release("5.10.81-gki", "5.10.81-gki SMP preempt mod_unload aarch64")
        abi.check_release("5.10.81", "5.10.81 SMP mod_unload aarch64")
        abi.check_release("5.10.81-gki-dirty",
                          "5.10.81-gki-dirty SMP preempt aarch64")

    def test_exact_compiled_kernelrelease_required(self):
        for release, vermagic in (
            ("5.10.81-gki", "5.10.81 SMP aarch64"),
            ("5.10.81", "5.10.81-gki SMP aarch64"),
            ("5.10.82-gki", "5.10.82-gki SMP aarch64"),
            ("5.10.810", "5.10.810 SMP aarch64"),
            ("5.10.81-testing extra", "5.10.81-testing extra SMP"),
        ):
            with self.subTest(release=release, vermagic=vermagic):
                with self.assertRaises(ValueError):
                    abi.check_release(release, vermagic)

    def test_real_oem_export_and_actual_elf_definition(self):
        exports = abi.check_abi(*fixture())
        self.assertEqual(exports, list(abi.REQUIRED_EXPORTS))

    def test_reject_unrelated_provider(self):
        with self.assertRaisesRegex(ValueError, "Module.symvers export"):
            abi.check_abi(*fixture(module="drivers/regulator/wl2866d_wrong"))

    def test_reject_missing_power_api(self):
        symvers, nm = fixture()
        symvers = "\n".join(
            row for row in symvers.splitlines()
            if "wl2866d_camera_power_down_eeprom" not in row
        )
        with self.assertRaisesRegex(ValueError, "down_eeprom"):
            abi.check_abi(symvers, nm)

    def test_reject_undefined_elf_symbol_even_if_symvers_exists(self):
        symvers, nm = fixture()
        nm = nm.replace("wl2866d_camera_power_up T", "wl2866d_camera_power_up U")
        with self.assertRaisesRegex(ValueError, "actual OEM"):
            abi.check_abi(symvers, nm)


if __name__ == "__main__":
    unittest.main()
