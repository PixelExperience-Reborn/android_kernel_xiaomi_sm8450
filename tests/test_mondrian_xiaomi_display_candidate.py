"""Pure regression coverage for the mondrian-only Xiaomi Display source gate."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "xiaomi_display_gate", ROOT / "tools/verify_mondrian_xiaomi_display_candidate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MiCodeDisplayContractTests(unittest.TestCase):
    def test_provenance_does_not_claim_mondrian_hardware(self):
        self.assertEqual(module.DEVICE, "mondrian")
        self.assertEqual(module.KERNEL_VERSION, "5.10.81")
        self.assertTrue(module.OEM_REFERENCE_REPO.startswith("MiCode/"))
        self.assertEqual(len(module.OEM_REFERENCE_COMMIT), 40)
        self.assertEqual(len(module.OEM_BLOBS), 4)
        self.assertNotIn("LineageOS", module.OEM_REFERENCE_REPO)

    def test_git_blob_hash_is_exact_git_object_format(self):
        import hashlib
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "source.c"
            path.write_bytes(b"kernel source\\n")
            expected = hashlib.sha1(b"blob 14\\0kernel source\\n").hexdigest()
            self.assertEqual(module.source_blob_sha(path), expected)

    def test_reject_missing_or_modified_xiaomi_reference(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            path = root / "src"
            path.write_text("old")
            with self.assertRaisesRegex(module.SourceAuditError, "drift"):
                module.verify_pinned_blobs(
                    root, {"src": "0" * 40}, "Xiaomi")
            with self.assertRaisesRegex(module.SourceAuditError, "missing"):
                module.verify_pinned_blobs(
                    root, {"not-present": "0" * 40}, "Xiaomi")

    def test_reject_wrong_reference_commit(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / ".git").mkdir()
            with patch.object(module.subprocess, "check_output",
                              return_value="deadbeef\\n"):
                with self.assertRaisesRegex(module.SourceAuditError, "wrong Xiaomi"):
                    module.verify_oem_reference(root)

    def test_missing_mondrian_kernel_is_never_approved(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaises(module.SourceAuditError):
                module.inspect_mondrian_kernel(Path(name))

    def test_selected_display_gap_is_reported_not_marked_qualified(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for relative in module.QUALCOMM_BLOBS:
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text("Qualcomm WAIPIO display")
            (root / "Makefile").write_text(
                "VERSION = 5\\nPATCHLEVEL = 10\\nSUBLEVEL = 81\\n")
            config = root / "arch/arm64/configs/vendor/mondrian_GKI.config"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text("# mondrian")
            with patch.object(module, "verify_pinned_blobs"):
                report = module.inspect_mondrian_kernel(root)
            self.assertFalse(report["production_display_allowed"])
            self.assertFalse(report["mondrian_udfps_lhbm_qualified"])
            self.assertFalse(report["physical_device_verified"])
            self.assertEqual(report["device"], "mondrian")
            (root / "techpack/display/msm/mi_disp").mkdir()
            with patch.object(module, "verify_pinned_blobs"):
                with self.assertRaisesRegex(
                        module.SourceAuditError, "requalify"):
                    module.inspect_mondrian_kernel(root)


if __name__ == "__main__":
    unittest.main()
