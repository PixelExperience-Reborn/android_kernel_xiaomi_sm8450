import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_public_evidence import git_blob_sha, load_manifest, validate_content


class ReferenceEvidenceTests(unittest.TestCase):
    def test_local_evidence_schema_valid(self):
        inventory, evidence, sources = load_manifest()
        self.assertEqual(len(sources), 5)
        self.assertEqual(len(evidence["files"]), 11)
        self.assertEqual(inventory["target"]["device"], "mondrian")
        self.assertEqual(
            {e["role"] for e in evidence["files"]},
            set(sources),
        )

    def test_goodix_mismatch_has_two_distinct_pinned_facts(self):
        _, evidence, _ = load_manifest()
        files = {(e["role"], e["path"]): e for e in evidence["files"]}
        official = files[("controller_vendor_touch", "goodix_brl_spi.c")]
        mondrian = files[("devicetree_reference", "qcom/mondrian-sm8475.dtsi")]
        self.assertIn('.compatible = "goodix,brl-d"', official["must_contain"])
        self.assertIn("goodix,gt9916S", official["must_not_contain"])
        self.assertIn('compatible = "goodix,gt9916S"', mondrian["must_contain"])
        self.assertIn('compatible = "goodix,fingerprint"', mondrian["must_contain"])

    def test_blob_hash_is_real_git_blob_sha(self):
        raw = b"hello\n"
        # Hash Git's 'blob <size>\\0<bytes>' wire representation.
        expected = hashlib.sha1(b"blob 6" + bytes([0]) + raw).hexdigest()
        self.assertEqual(git_blob_sha(raw), expected)

    def test_content_validation_fails_closed(self):
        raw = b"goodix,brl-d\n"
        e = {
            "blob_sha": git_blob_sha(raw),
            "must_contain": ["goodix,brl-d"],
            "must_not_contain": ["goodix,gt9916S"],
        }
        self.assertEqual(validate_content(raw, e), [])
        self.assertTrue(validate_content(b"goodix,gt9916S\n", e))
        self.assertTrue(validate_content(b"wrong\n", e))

    def test_duplicate_module_inventory_is_exact(self):
        raw = b"gh_virt_wdt.ko\nqcom_wdt_core.ko\ngh_virt_wdt.ko\nqcom_wdt_core.ko\n"
        e = {
            "blob_sha": git_blob_sha(raw),
            "must_contain": ["gh_virt_wdt.ko", "qcom_wdt_core.ko"],
            "module_list": {
                "entries": 4,
                "unique": 2,
                "duplicates": ["gh_virt_wdt.ko", "qcom_wdt_core.ko"],
            },
        }
        self.assertEqual(validate_content(raw, e), [])
        e["module_list"]["entries"] = 3
        self.assertTrue(validate_content(raw, e))


if __name__ == "__main__":
    unittest.main()
