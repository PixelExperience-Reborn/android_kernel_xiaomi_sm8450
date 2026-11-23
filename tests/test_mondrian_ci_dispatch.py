"""Prevent source-only pushes from starting a Full LTO Display/MMRM build."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/mondrian-oem-display-coherent-abi.yml"


class ManualFullBuildContract(unittest.TestCase):
    def test_source_checks_still_run_on_push(self):
        text = WORKFLOW.read_text()
        triggers = text.split("jobs:\n", 1)[0]
        self.assertIn("\n  push:\n", triggers)
        self.assertIn("\n  workflow_dispatch:\n", triggers)
        self.assertIn("  source:\n    runs-on: ubuntu-24.04", text)
        self.assertIn("python3 tools/verify_official_qualcomm_display.py", text)

    def test_full_oem_link_requires_manual_dispatch(self):
        text = WORKFLOW.read_text()
        self.assertIn(
            "  compile:\n"
            "    # Full OEM vmlinux/Module.symvers and Qualcomm Display/MMRM are expensive.\n",
            text,
        )
        self.assertIn(
            "    if: github.event_name == 'workflow_dispatch'\n"
            "    needs: source",
            text,
        )
        self.assertIn(
            'make -C kernel O="$RUNNER_TEMP/mondrian-out" -j3 vmlinux Image modules',
            text,
        )
        self.assertIn("Attempt real Qualcomm SDE/DSI msm_drm.ko build", text)


if __name__ == "__main__":
    unittest.main()
