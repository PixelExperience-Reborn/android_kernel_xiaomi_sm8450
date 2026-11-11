# Goodix Berlin D touchscreen — mondrian (POCO F5 Pro / Redmi K60)

**Kernel foundation:** official Xiaomi `MiCode/Xiaomi_Kernel_OpenSource`
`mondrian-s-oss@989b27aa8391a2ede9b067b53877c4c3343955fe` (Linux 5.10.81).

**Missing kernel component:** Xiaomi did not publish the Goodix Berlin
touchscreen driver used by mondrian's GT9916S controller.

**Direct manufacturer source:** `goodix/goodix_ts_berlin`, immutable
Git commit `6c4b81587d43cf4ebf59cc63fe2916d77e4e8ce2`. Full
manufacturer driver source and its `LICENSE` are included here with
original file-specific SPDX/copyright notices. This imports **only the
missing touchscreen driver**, not any LF52406 kernel, device tree,
LineageOS platform, unrelated vendor drivers or proprietary firmware.

**Device reference (not an imported DT):** published modern
`mondrian-sm8475.dtsi`, reference Git blob
`59cb230a704b67b3f8800682937bbec2a9e09f9c`, specifies:
GT9916S / Berlin D, QUPv3 SPI, 15 MHz max bus, IRQ GPIO21, reset
GPIO20, AVDD GPIO71, `goodix,panel-max-x=14400`,
`goodix,panel-max-y=32000`,
`goodix_firmware_m11a.bin` and `goodix_cfg_group_m11a.bin`.
Separate `goodix,fingerprint` (UDFPS) does NOT use this touch module.

## Deliberate hardware adaptation of manufacturer code

- Added `goodix,gt9916S` SPI compatible and Berlin D identification.
- Selected SPI only, retaining the manufacturer's Berlin D SPI read
  framing; excluded I2C objects from the mondrian build.
- Enabled `CONFIG_TOUCHSCREEN_GOODIX_BRL=m` in native mondrian config.
- Retained Goodix firmware/config names from Device Tree, GPL source
  licensing and upstream touchscreen/gesture/inspection support.
- Balanced platform driver cleanup if SPI registration fails.

## Blocking validation before hardware release

Compile with pinned official Android LLVM, check module vermagic and
`Module.symvers`, test power/IRQ/pinctrl/firmware and display resume,
touch coordinates, multi-touch, blank/unblank, gesture, touch latency,
robust handling of invalid frames and touchscreen interaction with
fingerprint-on-display. Neither the manufacturer baseline nor simple
OF-compatible matching proves all those behaviors for this phone.

The source branch remains Draft, and `seventeen` stays unchanged.
