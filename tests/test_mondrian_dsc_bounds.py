"""Regression gates for the native Qualcomm DSC parser used by mondrian.

These tests check the C source's fail-closed preconditions. The compile
workflow separately verifies the actual msm_drm.ko and OEM kernel ABI.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "techpack/display/msm/dsi/dsi_panel.c"
HELPER = ROOT / "techpack/display/msm/sde_dsc_helper.c"


class MondrianDscBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        panel = PANEL.read_text(encoding="utf-8")
        start = panel.index("static int dsi_panel_parse_dsc_params(")
        end = panel.index("static int dsi_panel_parse_vdc_params(", start)
        cls.parser = panel[start:end]
        cls.dsc = HELPER.read_text(encoding="utf-8")

    def test_real_calculator_has_slice_height_minus_one_divisor(self):
        self.assertIn("DIV_ROUND_UP(data, (dsc->slice_height - 1))", self.dsc)

    def test_parser_rejects_height_one_before_assigning_slice_height(self):
        guard = "if (data < 2 || data > mode->timing.v_active)"
        self.assertIn(guard, self.parser)
        self.assertLess(self.parser.index(guard),
                        self.parser.index("priv_info->dsc.config.slice_height = data;"))
        section = self.parser[self.parser.index(guard):
                              self.parser.index("priv_info->dsc.config.slice_height = data;")]
        self.assertIn("rc = -EINVAL;", section)
        self.assertIn("goto error;", section)

    def test_dsc_picture_dimensions_bound_to_pps_16bit_fields(self):
        section = self.parser[self.parser.index("if (!mode->timing.h_active"):
                              self.parser.index('qcom,mdss-dsc-version')]
        for value in ("!mode->timing.h_active", "!mode->timing.v_active",
                      "mode->timing.h_active > 0xffff",
                      "mode->timing.v_active > 0xffff"):
            self.assertIn(value, section)
        self.assertIn("return -EINVAL;", section)

    def test_dsc_bpp_rejected_before_shift_and_calculator(self):
        guard = "if (!data || data > 0x3f)"
        self.assertIn(guard, self.parser)
        self.assertLess(self.parser.index(guard),
                        self.parser.index("priv_info->dsc.config.bits_per_pixel = data << 4;"))
        self.assertLess(self.parser.index(guard),
                        self.parser.index("rc = sde_dsc_populate_dsc_config("))
        region = self.parser[self.parser.index(guard):
                             self.parser.index("priv_info->dsc.config.bits_per_pixel = data << 4;")]
        self.assertIn("goto error;", region)

    def test_original_nonzero_width_modulo_guard_remains(self):
        block = self.parser[self.parser.index("invalid zero DSC slice width"):]
        self.assertIn("intf_width % priv_info->dsc.config.slice_width", block)


if __name__ == "__main__":
    unittest.main()
