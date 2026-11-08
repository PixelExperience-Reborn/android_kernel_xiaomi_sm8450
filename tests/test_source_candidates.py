import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "source-candidates.json"

EXPECTED_ROLES = {
    "oem_kernel",
    "controller_vendor_touch",
    "modern_kernel_reference",
    "module_reference",
    "devicetree_reference",
}


class CandidateInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(FILE.read_text(encoding="utf-8"))
        cls.by_role = {item["role"]: item for item in cls.cfg["references"]}

    def test_schema_and_target(self):
        self.assertEqual(self.cfg["schema_version"], 2)
        self.assertEqual(self.cfg["target"]["project"], "PixelExperience-Reborn")
        self.assertEqual(self.cfg["target"]["device"], "mondrian")
        self.assertEqual(self.cfg["target"]["soc"], "SM8475")
        self.assertEqual(self.cfg["target"]["android_base"], "AOSP 17")

    def test_commit_and_tree_ids_are_distinct_and_immutable(self):
        self.assertEqual(set(self.by_role), EXPECTED_ROLES)
        self.assertEqual(len(self.cfg["references"]), len(EXPECTED_ROLES))
        for item in self.cfg["references"]:
            with self.subTest(repo=item["repository"]):
                self.assertRegex(item["source_commit_sha"], r"^[0-9a-f]{40}$")
                self.assertRegex(item["source_tree_sha"], r"^[0-9a-f]{40}$")
                self.assertNotEqual(item["source_commit_sha"], item["source_tree_sha"])
                self.assertIn(
                    item["classification"],
                    {"read_only_compatibility_reference", "incomplete_untested_reference"},
                )

    def test_no_premature_qualification(self):
        for key in (
            "selected_kernel_source", "selected_module_source",
            "selected_devicetree_source", "selected_toolchain",
            "qualified_firmware",
        ):
            self.assertIsNone(self.cfg[key], key)
        self.assertEqual(self.cfg["target"]["kernel_branch"], "unselected")
        self.assertFalse(self.cfg["target"]["build_proven"])
        self.assertFalse(self.cfg["target"]["boot_proven"])
        self.assertTrue(self.cfg["gates"])
        self.assertFalse(any(self.cfg["gates"].values()))

    def test_versions_and_license(self):
        self.assertEqual(self.by_role["oem_kernel"]["kernel_version"], "5.10.81")
        self.assertEqual(self.by_role["modern_kernel_reference"]["kernel_version"], "5.10.269")
        self.assertEqual(
            self.by_role["controller_vendor_touch"]["repository"],
            "goodix/goodix_ts_berlin",
        )
        self.assertEqual(
            self.by_role["controller_vendor_touch"]["license"], "GPL-2.0-only"
        )

    def test_exact_touch_contract_is_blocked(self):
        contract = self.cfg["hardware_reference_contract"]["touch"]
        self.assertEqual(contract["spi_compatible"], "goodix,gt9916S")
        self.assertEqual(contract["manufacturer_driver_compatible"], "goodix,brl-d")
        self.assertNotEqual(contract["spi_compatible"], contract["manufacturer_driver_compatible"])
        self.assertFalse(contract["known_match"])
        self.assertFalse(contract["manufacturer_port_approved"])
        self.assertIsNone(contract["measured_controller_id"])
        self.assertIsNone(contract["measured_firmware_version"])
        self.assertIsNone(contract["measured_panel_revision"])
        self.assertEqual(contract["firmware_name"], "goodix_firmware_m11a.bin")

    def test_oem_module_duplicates_are_not_mistaken_for_validated_build(self):
        mods = self.cfg["hardware_reference_contract"]["oem_modules"]
        self.assertEqual(mods["entries"], 106)
        self.assertEqual(mods["unique"], 104)
        self.assertEqual(set(mods["duplicates"]), {"gh_virt_wdt.ko", "qcom_wdt_core.ko"})
        self.assertFalse(mods["resolved"])

    def test_qpr_support_and_exclusions(self):
        status = self.cfg["hardware_reference_contract"]["android17_qpr1_plus"]
        self.assertFalse(status["gki_5_10_officially_supported"])
        self.assertFalse(status["supported_kernel_selected"])
        self.assertFalse(status["vendor_kmi_verified"])
        self.assertIn("FM radio", self.cfg["excluded"])
        self.assertIn("ROM-specific LineageOS product dependencies", self.cfg["excluded"])
        self.assertIn("test AVB keys", self.cfg["excluded"])


if __name__ == "__main__":
    unittest.main()
