#!/usr/bin/env python3
"""Source-level guard for OEM-first mondrian GT9916S Goodix driver.

This does NOT replace compilation, Module.symvers or physical touch tests.
"""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "drivers/input/touchscreen/goodix_berlin_driver"
def require(ok, message):
    if not ok:
        raise SystemExit("[FAIL] " + message)
def main():
    core = (DRIVER / "goodix_ts_core.c").read_text()
    spi = (DRIVER / "goodix_brl_spi.c").read_text()
    utils = (DRIVER / "goodix_ts_utils.c").read_text()
    kconfig = (ROOT / "drivers/input/touchscreen/Kconfig").read_text()
    makefile = (ROOT / "drivers/input/touchscreen/Makefile").read_text()
    fragment = (ROOT / "arch/arm64/configs/vendor/mondrian_GKI.config").read_text()
    required = ["goodix_ts_core.c", "goodix_brl_hw.c", "goodix_brl_spi.c",
                "goodix_ts_utils.c", "goodix_brl_fwupdate.c",
                "goodix_ts_gesture.c", "goodix_ts_inspect.c",
                "goodix_ts_tools.c", "goodix_ts_dump.c", "goodix_ts_replay.c",
                "goodix_ts_core.h", "goodix_ts_replay_type.h", "LICENSE"]
    for filename in required:
        require((DRIVER / filename).is_file(), f"missing manufacturer file: {filename}")
    require('compatible = "goodix,gt9916S"' in spi, "GT9916S device-tree match absent")
    require('strstr(ic_name, "gt9916S")' in utils, "Berlin D identification missing")
    require('bus_inf->ic_type = IC_TYPE_BERLIN_D' in utils, "Berlin D protocol missing")
    require("SPI_READ_PREFIX_LEN - 1" in spi, "Berlin D read framing missing")
    require("goodix_spi_bus_init()" in core, "SPI driver registration missing")
    require("platform_driver_unregister(&goodix_ts_driver)" in core,
            "failed SPI registration does not unwind platform driver")
    require('source "drivers/input/touchscreen/goodix_berlin_driver/Kconfig"' in kconfig,
            "Kconfig not connected to OEM touchscreen subtree")
    require("obj-$(CONFIG_TOUCHSCREEN_GOODIX_BRL) += goodix_berlin_driver/" in makefile,
            "Goodix driver not connected to OEM Kbuild")
    require("CONFIG_TOUCHSCREEN_GOODIX_BRL=m" in fragment,
            "Goodix is not selected as mondrian module")
    driver_make = (DRIVER / "Makefile").read_text()
    require("goodix_brl_spi.o" in driver_make and "goodix_brl_i2c.o" not in driver_make,
            "mondrian Goodix must build SPI without I2C")
    require("goodix_firmware_m11a.bin" in (DRIVER / "MONDRIAN_SOURCE.md").read_text(),
            "firmware requirements not documented")
    print("[PASS] Complete manufacturer Goodix Berlin source and mondrian SPI binding")
    print("[PENDING] real LLVM module compile, firmware, FOD and device runtime")
if __name__ == "__main__":
    main()
