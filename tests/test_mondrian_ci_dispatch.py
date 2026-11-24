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

    def test_full_oem_link_requires_trusted_dispatch_or_marked_push(self):
        text = WORKFLOW.read_text()
        self.assertIn(
            "  compile:\n"
            "    # Full OEM vmlinux/Module.symvers and Qualcomm Display/MMRM are expensive.\n",
            text,
        )
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn("github.event_name == 'push'", text)
        self.assertIn("github.ref == 'refs/heads/bringup/a17-mondrian-oem-display-coherent-20261115'", text)
        self.assertIn("contains(github.event.head_commit.message, '[serverhive-qualification]')", text)
        self.assertIn("    needs: source", text)
        self.assertIn("group: mondrian-heavy", text)
        self.assertIn("labels: pe-mondrian-heavy", text)
        self.assertIn("runner.environment == 'self-hosted'", text)
        self.assertIn("runner.environment == 'github-hosted'", text)
        self.assertIn("external-modules/tools/config/mondrian_gki_hardening.config", text)
        self.assertIn("python3 external-modules/tools/verify_mondrian_kernel_hardening.py", text)
        self.assertIn("ref: 9aada12412cae4997eec4510e548d7f26c91b892", text)
        self.assertIn('make -C kernel O="$RUNNER_TEMP/mondrian-out" -j8 vmlinux Image modules', text)
        self.assertIn(
            'make -C kernel O="$RUNNER_TEMP/mondrian-out" -j3 vmlinux Image modules',
            text,
        )
        self.assertIn("Attempt real Qualcomm SDE/DSI msm_drm.ko build", text)


if __name__ == "__main__":
    unittest.main()
