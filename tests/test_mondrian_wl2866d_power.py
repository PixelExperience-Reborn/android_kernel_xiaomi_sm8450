"""Contract tests for functional Xiaomi WL2866D camera power reliability.

The proof of C build is the separate LLVM23 OEM kernel compile job.
These regression guards check that the independent AOSP17 adaptation
retains manufacturer hardware values while correcting indexing, rollback,
atomic power transitions and Linux driver lifetime.
"""
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "drivers/misc/wl2866d.c").read_text()
HEADER = (ROOT / "include/misc/wl2866d.h").read_text()


def section(start, end):
    return SRC.split(start, 1)[1].split(end, 1)[0]


class XiaomiWL2866DPowerTests(unittest.TestCase):
    def test_preserve_exact_oem_voltage_registers(self):
        for original in ('{0x03, 0x54}', '{0x04, 0x64}',
                         '{0x05, 0x30}', '{0x06, 0x30}',
                         '{0x0E, 0x0F}', '{0x0E, 0x00}'):
            self.assertIn(original, SRC)
        for symbol in ("wl2866d_camera_power_up", "wl2866d_camera_power_down",
                       "wl2866d_camera_power_up_eeprom",
                       "wl2866d_camera_power_down_eeprom",
                       "wl2866d_camera_power_up_all"):
            self.assertIn("EXPORT_SYMBOL(" + symbol + ");", SRC)
        self.assertIn('"xiaomi,wl2866d"', SRC)

    def test_invalid_power_ids_rejected_before_index(self):
        power = section("static int wl2866d_camera_set_output(",
                        "int wl2866d_camera_power_up(")
        checked = power.index("if (out_iotype < WL2866D_FIRST_POWER_SEQ")
        indexed = power.index("atomic_read(&wl2866d_use_count[channel])")
        self.assertLess(checked, indexed)
        self.assertIn("out_iotype > WL2866D_FIRST_POWER_SEQ + LAST_POWER_CH", power)
        self.assertIn("out_delay < 0", power)
        self.assertIn("#define WL2866D_FIRST_POWER_SEQ 13", SRC)
        self.assertIn("channel = out_iotype - WL2866D_FIRST_POWER_SEQ", power)

    def test_i2c_failure_does_not_publish_false_reference_count(self):
        power = section("static int wl2866d_camera_set_output(",
                        "int wl2866d_camera_power_up(")
        write_enable = power.index("ret = wl2866d_i2c_write(camera_chip,\n"
                                   "\t\t\t\twl2866d_on_config[VOL_ENABLE].reg,")
        assert_good = power.index("if (ret < 0)\n\t\tgoto unlock;", write_enable)
        set_ref = power.index("atomic_set(&wl2866d_use_count[channel], enable ? 1 : 0)")
        self.assertLess(write_enable, assert_good)
        self.assertLess(assert_good, set_ref)
        self.assertIn("atomic_inc(&wl2866d_use_count[channel]);", power)
        self.assertIn("atomic_dec(&wl2866d_use_count[channel]);", power)
        self.assertIn("if (users <= 0)", power)
        self.assertIn("if (users == INT_MAX)", power)

    def test_one_lock_covers_full_smbus_read_modify_write(self):
        power = section("static int wl2866d_camera_set_output(",
                        "int wl2866d_camera_power_up(")
        self.assertIn("static DEFINE_MUTEX(wl2866d_mutex)", SRC)
        self.assertEqual(power.count("mutex_lock(&wl2866d_mutex);"), 1)
        self.assertEqual(power.count("mutex_unlock(&wl2866d_mutex);"), 1)
        self.assertLess(power.index("mutex_lock(&wl2866d_mutex);"),
                        power.index("ret = wl2866d_i2c_read(camera_chip,"))
        self.assertLess(power.index("atomic_set(&wl2866d_use_count[channel]"),
                        power.index("mutex_unlock(&wl2866d_mutex);"))

    def test_preserve_existing_oem_delay_limit_no_int_overflow(self):
        power = section("static int wl2866d_camera_set_output(",
                        "int wl2866d_camera_power_up(")
        self.assertIn("out_delay > MAX_DELAY_TIME / DELAY_SETP", power)
        self.assertIn("delay_us = MAX_DELAY_TIME;", power)
        self.assertIn("usleep_range(delay_us, delay_us + 100)", power)

    def test_eeprom_enable_disable_uses_valid_device_and_rollback(self):
        down = section("int wl2866d_camera_power_down_all(void)",
                       "static int wl2866d_camera_set_output(")
        up = section("int wl2866d_camera_power_up_all(void)",
                     "EXPORT_SYMBOL(wl2866d_camera_power_up_all)")
        self.assertIn("if (!camera_chip)", down)
        self.assertIn("if (!camera_chip)", up)
        self.assertIn("if (ret >= 0)\n\t\tclear_use_count(0)", down)
        self.assertIn("clear_use_count(1)", up)

    def test_probe_teardown_does_not_leave_stale_global_device(self):
        probe = section("static int wl2866d_probe(", "static int wl2866d_remove(")
        remove = section("static int wl2866d_remove(", "#ifdef CONFIG_PM_SLEEP")
        self.assertIn("devm_kzalloc", probe)
        self.assertIn("devm_gpio_request", SRC)
        self.assertIn("if (camera_chip) {", probe)
        self.assertIn("camera_chip = chip;", probe)
        self.assertIn("if (camera_chip == chip)\n\t\tcamera_chip = NULL;", remove)
        self.assertIn("sysfs_remove_group", remove)
        self.assertIn("wl2866d_disable_power(chip);", remove)
        self.assertNotIn("devm_kfree(chip->dev, chip);", remove)
        self.assertNotIn("mutex_init(&wl2866d_mutex)", SRC)


if __name__ == "__main__":
    unittest.main()
