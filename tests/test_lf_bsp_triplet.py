import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_lf_bsp_triplet import validate_lock, git_blob, ROLES, LOCK


class LfCandidateTripletTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lock = json.loads(LOCK.read_text(encoding="utf-8"))

    def test_source_lock_has_immutable_real_three_repo_sources(self):
        sources = validate_lock(self.lock)
        self.assertEqual(set(sources), ROLES)
        self.assertEqual(sources["kernel"]["commit_sha"], "283772ceb84491fd446e340fd211d45fb9dd9a36")
        self.assertEqual(sources["modules"]["commit_sha"], "91cdb1347970ae98291986926eb16bf1b172138e")
        self.assertEqual(sources["devicetrees"]["commit_sha"], "99f1330d8dce0c80de5a19f425d0a118b2eb7fe3")

    def test_kernel_is_5_10_trial_only(self):
        k = next(s for s in self.lock["sources"] if s["role"] == "kernel")
        make = next(f for f in k["files"] if f["path"] == "Makefile")
        self.assertEqual(set(make["contains"]), {"VERSION = 5", "PATCHLEVEL = 10", "SUBLEVEL = 269"})
        self.assertFalse(self.lock["android17_policy"]["gki_5_10_supported_on_qpr1_plus"])

    def test_header_v3_and_rom_v4_not_silently_equated(self):
        c = self.lock["known_conflicts"]
        self.assertEqual(c["standalone_qualcomm_boot_header"], 3)
        self.assertEqual(c["rom_target_board_header_reference"], 4)
        self.assertFalse(c["boot_header_layout_resolved"])

    def test_qualcomm_ack_and_modules_layout_must_be_selected_later(self):
        l = self.lock["build_layout"]
        self.assertEqual(l["ack_checkout"], "common")
        self.assertEqual(l["msm_kernel_checkout"], "msm-kernel")
        self.assertEqual(l["kernel_build_config"], "msm-kernel/build.config.msm.waipio")
        self.assertIsNone(l["ack_kernel_commit"])
        self.assertIsNone(l["compiler_revision"])
        self.assertFalse(any(self.lock["gates"].values()))

    def test_missing_or_mutated_source_is_blocked(self):
        changed = copy.deepcopy(self.lock)
        changed["sources"][0]["root_tree_sha"] = "0" * 40
        # Still structurally valid: immutable remote identity check must reject it online.
        self.assertIn("kernel", validate_lock(changed))
        changed = copy.deepcopy(self.lock)
        changed["sources"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            validate_lock(changed)
        changed = copy.deepcopy(self.lock)
        changed["gates"]["kernel_elf_compiled"] = True
        with self.assertRaisesRegex(ValueError, "prematurely"):
            validate_lock(changed)

    def test_unreviewed_boot_header_and_touch_claims_blocked(self):
        changed = copy.deepcopy(self.lock)
        changed["known_conflicts"]["boot_header_layout_resolved"] = True
        with self.assertRaisesRegex(ValueError, "boot header"):
            validate_lock(changed)
        changed = copy.deepcopy(self.lock)
        changed["known_conflicts"]["touch_driver_replacement_approved"] = True
        with self.assertRaisesRegex(ValueError, "Goodix"):
            validate_lock(changed)

    def test_new_google_android_clang_is_pinned_without_disabling_warnings(self):
        c = self.lock["diagnostic_android_clang"]
        self.assertEqual(c["path"], "clang-r614150")
        self.assertEqual(c["llvm_major"], 23)
        self.assertEqual(c["source_commit_sha"],
                         "c9ed23e2ba198658b630d4b10e09fa980cd43119")
        self.assertFalse(c["production_approved"])
        self.assertTrue(c["strict_frame_warnings_required"])
        self.assertIsNone(c["qualcomm_module_symvers_compatible"])
        self.assertTrue(c["aosp17_platform_clang_unmodified"])
        workflow = (ROOT / ".github/workflows/lf-image-diagnostic.yml").read_text()
        self.assertIn("tools/fetch_modern_android_clang.sh", workflow)
        self.assertIn("clang-r614150", workflow)
        self.assertNotIn("KCFLAGS=-Wno-error", workflow)
        self.assertNotIn("clang lld llvm make", workflow)

    def test_git_blob_digest_is_not_regular_file_sha(self):
        self.assertEqual(git_blob(b"hello\n"),
                         "ce013625030ba8dba906f756967f9e9ca394464a")

    def test_repositories_are_references_not_installed_sources(self):
        for s in self.lock["sources"]:
            self.assertFalse(s["materialized_in_pe"])
        self.assertIn("no FM radio in PE device product", self.lock["explicit_exclusions"])
        self.assertIn("no test AVB keys", self.lock["explicit_exclusions"])


if __name__ == "__main__":
    unittest.main()
