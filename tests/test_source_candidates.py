import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "source-candidates.json"


class CandidateInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = json.loads(FILE.read_text(encoding="utf-8"))

    def test_target_is_exactly_mondrian(self):
        self.assertEqual(self.cfg["target"]["device"], "mondrian")
        self.assertEqual(self.cfg["target"]["soc"], "SM8475")
        self.assertEqual(self.cfg["target"]["android_base"], "AOSP 17")

    def test_all_reference_roles_have_immutable_tree_sha(self):
        expected = {"oem_kernel", "modern_kernel_reference", "module_reference", "devicetree_reference"}
        roles = {s["role"] for s in self.cfg["references"]}
        self.assertEqual(roles, expected)
        for item in self.cfg["references"]:
            with self.subTest(repo=item["repository"]):
                self.assertRegex(item["source_tree_sha"], r"^[0-9a-f]{40}$")
                self.assertIn(item["classification"], {"read_only_compatibility_reference", "incomplete_untested_reference"})

    def test_no_sources_preselected_or_falsely_qualified(self):
        for name in ("selected_kernel_source", "selected_module_source", "selected_devicetree_source", "selected_toolchain", "qualified_firmware"):
            self.assertIsNone(self.cfg[name], name)
        self.assertFalse(self.cfg["target"]["build_proven"])
        self.assertFalse(self.cfg["target"]["boot_proven"])
        self.assertTrue(self.cfg["gates"])
        self.assertFalse(any(self.cfg["gates"].values()))

    def test_oem_vs_later_kernel_version_evidence(self):
        by_role = {x["role"]: x for x in self.cfg["references"]}
        self.assertEqual(by_role["oem_kernel"]["kernel_version"], "5.10.81")
        self.assertEqual(by_role["modern_kernel_reference"]["kernel_version"], "5.10.269")
        self.assertNotEqual(by_role["oem_kernel"]["source_tree_sha"], by_role["modern_kernel_reference"]["source_tree_sha"])

    def test_no_fm_radio_inclusion(self):
        self.assertIn("FM radio", self.cfg["excluded"])


if __name__ == "__main__":
    unittest.main()
