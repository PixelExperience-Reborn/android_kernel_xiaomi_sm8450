"""Mondrian LHBM panel lifecycle, native command completion and readiness."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PANEL_C = (ROOT / "techpack/display/msm/dsi/dsi_panel.c").read_text()
PANEL_H = (ROOT / "techpack/display/msm/dsi/dsi_panel.h").read_text()
FOD = (ROOT / "techpack/display/msm/mondrian/mondrian_fod.c").read_text()
MODEL = (ROOT / "techpack/display/msm/mondrian/mondrian_lhbm_fsm.c").read_text()


def function_body(source, start, end):
    a = source.index(start)
    b = source.index(end, a + len(start))
    return source[a:b]


class MondrianLhbmPanelLifecycle(unittest.TestCase):
    def test_source_enabled_only_on_waipio_with_unqualified_factory(self):
        self.assertIn('#ifdef CONFIG_ARCH_WAIPIO\n#include "../mondrian/mondrian_lhbm_fsm.h"', PANEL_H)
        self.assertIn("struct mondrian_lhbm_fsm mondrian_lhbm;", PANEL_H)
        getter = function_body(PANEL_C, "struct dsi_panel *dsi_panel_get(", "int dsi_panel_get_dfps_caps(")
        self.assertIn("mondrian_lhbm_init(&panel->mondrian_lhbm, false);", getter)
        self.assertIn("#ifdef CONFIG_ARCH_WAIPIO", getter)
        self.assertIn("factory_qualified = factory_qualified;", MODEL)

    def test_only_attached_panel_can_drive_fod_and_report_readiness(self):
        helper = function_body(PANEL_C, "static void dsi_panel_mondrian_lhbm_event_locked(",
                               "static void dsi_dce_prepare_pps_header(")
        self.assertIn("if (panel->mondrian_fod)", helper)
        self.assertIn("mondrian_fod_event_locked(panel, event)", helper)
        self.assertIn("mondrian_lhbm_panel_event(", helper)
        self.assertIn('"xiaomi,mondrian-m11a-fod"', FOD)
        self.assertIn("id != 0x4d31314100420200ULL", FOD)
        worker = function_body(FOD, "static void ready_worker(", "static int sync_panel(")
        self.assertLess(worker.index("f->token != fsm->token"), worker.index("publish(f, MI_FOD_READY"))
        self.assertLess(worker.index("ktime_us_delta"), worker.index("mondrian_lhbm_complete("))
        self.assertLess(worker.index("m11a_host_ready(d)"), worker.index("publish(f, MI_FOD_READY"))

    def test_on_follows_successful_panel_dsi_init_under_lock(self):
        enable = function_body(PANEL_C, "int dsi_panel_enable(", "int dsi_panel_post_enable(")
        self.assertLess(enable.index("mutex_lock(&panel->panel_lock)"),
                        enable.index("dsi_panel_tx_cmd_set(panel, DSI_CMD_SET_ON"))
        self.assertLess(enable.index("DSI_CMD_SET_CMD_ON"),
                        enable.index("MONDRIAN_LHBM_PANEL_ON"))
        self.assertLess(enable.index("panel->panel_initialized = true;\n#ifdef CONFIG_ARCH_WAIPIO"),
                        enable.index("MONDRIAN_LHBM_PANEL_ON"))
        self.assertLess(enable.index("MONDRIAN_LHBM_PANEL_ON"),
                        enable.rindex("mutex_unlock(&panel->panel_lock)"))

    def test_off_revoke_precedes_dsi_off_or_esd_and_power_down(self):
        disable = function_body(PANEL_C, "int dsi_panel_disable(", "int dsi_panel_unprepare(")
        self.assertLess(disable.index("mutex_lock(&panel->panel_lock)"),
                        disable.index("MONDRIAN_LHBM_ESD_DETECTED"))
        self.assertLess(disable.index("MONDRIAN_LHBM_PANEL_QUIESCE"),
                        disable.index("DSI_CMD_SET_OFF"))
        self.assertNotIn("MONDRIAN_LHBM_PANEL_OFF", disable)
        self.assertIn("atomic_read(&panel->esd_recovery_pending)", disable)
        power_down = PANEL_C[PANEL_C.index("int dsi_panel_post_unprepare("):]
        self.assertLess(power_down.index("dsi_panel_power_off(panel)"),
                        power_down.index("MONDRIAN_LHBM_PANEL_OFF"))
        self.assertLess(power_down.index("if (rc) {"),
                        power_down.index("MONDRIAN_LHBM_PANEL_OFF"))
        self.assertLess(power_down.index("goto error;"),
                        power_down.index("MONDRIAN_LHBM_PANEL_OFF"))
        self.assertLess(power_down.index("MONDRIAN_LHBM_PANEL_OFF"),
                        power_down.index("mutex_unlock(&panel->panel_lock)"))

    def test_shutdown_is_not_a_verified_poweroff_ack(self):
        self.assertIn("MONDRIAN_LHBM_PANEL_QUIESCE", MODEL)
        self.assertIn("power_off_pending = true;", MODEL)
        self.assertIn("power_off_pending = false;", MODEL)
        model_pre = function_body(MODEL,
                                  "case MONDRIAN_LHBM_PANEL_QUIESCE:",
                                  "case MONDRIAN_LHBM_PANEL_OFF:")
        self.assertNotIn("fsm->esd = false;", model_pre)
        self.assertNotIn("fsm->power_off_pending = false;", model_pre)
        self.assertIn("fsm->phase != MONDRIAN_LHBM_FAULT", model_pre)

    def test_doze_transitions_only_after_successful_panel_command(self):
        for start, end, cmd, event in (
            ("int dsi_panel_set_lp1(", "int dsi_panel_set_lp2(",
             "DSI_CMD_SET_LP1", "MONDRIAN_LHBM_DOZE_ENTER"),
            ("int dsi_panel_set_lp2(", "int dsi_panel_set_lp2_load(",
             "DSI_CMD_SET_LP2", "MONDRIAN_LHBM_DOZE_ENTER"),
            ("int dsi_panel_set_nolp(", "int dsi_panel_prepare(",
             "DSI_CMD_SET_NOLP", "MONDRIAN_LHBM_DOZE_EXIT"),
        ):
            with self.subTest(event=event, start=start):
                fn = function_body(PANEL_C, start, end)
                self.assertLess(fn.index(cmd), fn.index(event))
                self.assertIn("if (!rc)\n\t\tdsi_panel_mondrian_lhbm_event_locked(", fn)
                self.assertLess(fn.index("mutex_lock(&panel->panel_lock)"),
                                fn.index(event))
                self.assertLess(fn.index(event),
                                fn.index("mutex_unlock(&panel->panel_lock)"))

    def test_skip_panel_off_cannot_ack_physical_power_down(self):
        power_off = function_body(PANEL_C, "int dsi_panel_power_off(",
                                  "static int dsi_panel_tx_cmd_set(")
        post = PANEL_C[PANEL_C.index("int dsi_panel_post_unprepare("):]
        # Qualcomm returns zero for skip_panel_off despite never disabling rails.
        self.assertIn("if (panel->skip_panel_off)", power_off)
        self.assertRegex(
            post,
            r"if \(!panel->skip_panel_off\)\s*"
            r"dsi_panel_mondrian_lhbm_event_locked\(panel,\s*"
            r"MONDRIAN_LHBM_PANEL_OFF\);",
        )
        self.assertLess(post.index("dsi_panel_power_off(panel)"),
                        post.index("if (!panel->skip_panel_off)"))

    def test_generic_state_machine_stays_independent_of_panel_io(self):
        self.assertIn("MONDRIAN_LHBM_DISABLED", MODEL)
        self.assertNotIn("mipi_dsi_dcs_write(", MODEL)
        self.assertNotIn("MI_SET_LOCAL_HBM", MODEL)


if __name__ == "__main__":
    unittest.main()
