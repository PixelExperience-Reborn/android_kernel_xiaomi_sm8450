# PixelExperience-Reborn Android 17 — independent mondrian kernel/BSP audit

**State:** source inspection only. No kernel source has been copied into this
repository, no kernel/module/DTBO image has been built, and no boot has been
tested. Target: **POCO F5 Pro / Redmi K60 (mondrian, physical SM8475)**.
PE-Reborn source platform remains official **AOSP 17**, not another custom ROM.

## Verified reference snapshots (2026-11-08)

| Purpose | Public reference | Git tree SHA | Facts / caveats |
| --- | --- | --- | --- |
| Xiaomi OEM disclosure | [mondrian-s-oss](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/mondrian-s-oss) | `989b27aa8391a2ede9b067b53877c4c3343955fe` | `Makefile`: **5.10.81**; `build.config.msm.mondrian`, `modules.list.msm.mondrian`, `arch/arm64/configs/vendor/mondrian_GKI.config` exist. **Not an independently verified complete build**. |
| Goodix controller manufacturer | [goodix/goodix_ts_berlin](https://github.com/goodix/goodix_ts_berlin/tree/master) | `6c4b81587d43cf4ebf59cc63fe2916d77e4e8ce2` | **GPL-2.0**. Manufacturer supports **GT9916 (BerlinD)** and SPI; contains firmware update, ESD-related modules and gesture sources. **Not a validated mondrian driver yet.** |
| Later kernel compatibility reference | [LineageOS/android_kernel_xiaomi_sm8450](https://github.com/LineageOS/android_kernel_xiaomi_sm8450/tree/lineage-24.0) | `eff4b40407a1b6f1b1ab84554cbb540bcb495175` | `Makefile`: **5.10.269**; contains kernel-side Goodix Berlin driver and updated security. **Not the PE kernel source**. |
| Qualcomm external module inventory reference | [LineageOS/android_kernel_xiaomi_sm8450-modules](https://github.com/LineageOS/android_kernel_xiaomi_sm8450-modules/tree/lineage-24.0) | `3b30ba7df6608c97c0ba2d55d679a6b5987c4c66` | Thousands of external Qualcomm module sources incl. display, camera, audio, WLAN. **Not yet audited, selected or copied**. |
| Device tree / DTBO inventory reference | [LineageOS/android_kernel_xiaomi_sm8450-devicetrees](https://github.com/LineageOS/android_kernel_xiaomi_sm8450-devicetrees/tree/lineage-24.0) | `2e649a7f3e762903eedad43d8256b91e28b512d8` | mondrian SM8475, panel M11A, Goodix SPI touch node. **Not yet audited, selected or copied**. |

The SHA values above identify **Git tree snapshots**, not source-package checksums or
device firmware hashes. Before import, pin **commit SHA**, validate history,
license notices, redistribution terms and all dependent subprojects. The
source lists are evidence of historical contents, **not approval to merge**.

## Why Xiaomi `mondrian-s-oss` is insufficient as a default kernel

1. Xiaomi published a 5.10.81 tree for the original Android S OEM BSP.
   An Android 17 product needs further security updates and current Android
   platform interfaces while preserving Qualcomm SM8475 module compatibility.
   **Latest Linux patch number alone cannot establish ABI or boot safety**.
2. OEM build metadata contains `build.config.msm.mondrian`, which sources
   `common/build.config.common` and `common/build.config.aarch64` via
   `ROOT_DIR`, and can expect an external `msm-kernel` build layout.
   These contracts must be checked with a full manifest, toolchain and
   external module repositories; a single kernel Git checkout is not proof.
3. The OEM `mondrian-s-oss` tree is missing the newer
   `drivers/input/touchscreen/goodix_berlin_driver` directory present in the
   later kernel reference. This **does not prove** which version the phone
   currently runs, nor that the later implementation is correct. It is a
   concrete candidate for **source provenance, regression and API review**.
4. The original Xiaomi source contains `arch/arm64/configs/vendor/mondrian_GKI.config`,
   but the later kernel reference has its own divergent config fragments.
   Configs must be evaluated as a complete defconfig/fragment stack; never
   copy one fragment while assuming it selects every hardware driver.
5. No matched OEM `vendor_dlkm`, first-stage modules, DTBO, firmware blobs,
   exported KMI symbol set and `Module.symvers` were verified as one
   reproducible BOM. The separate module and DT repos are real dependencies,
   not optional cosmetic directories.

## Touchscreen and UDFPS: separate hardware paths

A *display driver* (DSI/DRM/panel) is **not** a *touch driver* (SPI input
controller). A newer display HAL in PE-Reborn does not automatically fix ghost
touches. The read-only mondrian DTS reference declares an SPI controller
`goodix,gt9916S`, firmware `goodix_firmware_m11a.bin`, configuration
`goodix_cfg_group_m11a.bin`, IRQ GPIO21 and reset GPIO20. These are **source
claims**, not yet confirmed against on-device IC identification.

Fingerprint is independently represented by a `goodix,fingerprint` node.
UDFPS requires a coherent kernel device, firmware/TEE vendor HAL, user-facing
AOSP Fingerprint AIDL adapter and panel illumination/HWC behavior. A Goodix
touchscreen and a Goodix fingerprint reader are different devices and drivers.

Required ghost-touch diagnosis: determine whether phantom events arise
from raw `/dev/input/event*`, correlate IRQ/recovery/ESD logs, firmware and
panel power state, and repeat tests with charger unplugged/plugged,
60/120 Hz, screen-off resume and a known-good vendor firmware baseline.
Record firmware/controller and panel revisions. No automated driver upgrade
without reproducible evidence, source diff review and hardware regression.

## Direct touch-driver candidate independent of custom ROMs

The actual controller manufacturer publishes its own
[Goodix Berlin Linux driver](https://github.com/goodix/goodix_ts_berlin)
with source files `goodix_brl_spi.c`, `goodix_brl_fwupdate.c`,
`goodix_ts_core.c`, `goodix_ts_gesture.c` and
`goodix_ts_inspect.c`. The upstream
[porting guide](https://github.com/goodix/goodix_ts_berlin/blob/master/docs/Porting_Guide.md)
explicitly maps **GT9916 to BerlinD** with SPI support. This is a
**more direct origin** for driver analysis than a ROM fork.

**Important incompatibility to audit:** the manufacturer guide documents
the generic DT `compatible = "goodix,brl-d"` for GT9916, whereas the
read-only mondrian device tree declares `goodix,gt9916S`. Never assume
one automatically matches the other: verify the exact driver of_match table,
chip revision/protocol, panel geometry and power/reset/IRQ contract.
Firmware blobs `goodix_firmware_m11a.bin` and
`goodix_cfg_group_m11a.bin` are separate versioned artifacts; a new
driver with a mismatched firmware/config can **create** ghost-touch faults
instead of fixing them.

The current mainline Linux Goodix Berlin implementation is another
reference, but its in-tree documentation/source explicitly notes missing
ESD management, firmware/config flashing and gesture handling. Those
features matter for a phone's actual input/suspend behavior. Do not
replace a functioning vendor driver with the simpler mainline driver
until this gap has been resolved. See:
https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/goodix_berlin_core.c

Next step: audit Goodix official source's license, commit history, SPI
compatible strings, event parsing, IRQ acknowledgement, ESD recovery and
firmware-loader logic against the actual mondrian firmware, then construct
a *device-specific* port with a host test and real touch trace. No driver
source is copied or compiled by this PR.

## Android 17 lifetime / kernel version gate

AOSP's published compatibility matrix lists Android 12/13 GKI **5.10**
for Android 17 initial release **but not Android 17 QPR1 and later**.
This is an official support boundary, not an assertion that all 5.10
kernels cease compiling. A cross-LTS uplift to 5.15/6.1/6.6 is **not** a
drop-in version bump: hardware drivers, DT, KMI, vendor modules, toolchain,
firmware and bootloader assumptions require a coordinated port. Before
declaring any Android17 QPR strategy, decide supported release/FCM targets
and prove compatibility end to end.

Source: https://source.android.com/docs/core/architecture/kernel/android-common

## Required steps before any source import or kernel build claim

- [ ] Select a *lawfully redistributable* full kernel baseline; preserve
      authorship and all GPL/other licenses and complete patch provenance.
- [ ] Reconcile OEM 5.10.81 with audited upstream Android ACK/Linux stable
      security fixes; do not assume the later ROM-specific source is a
      direct upstream or appropriate complete replacement.
- [ ] Pin complete source manifest: kernel commit, module commits,
      devicetree commit, firmware version, board/device revision and toolchain.
- [ ] Verify final `.config` including touchscreen/FOD, UFS, display, camera,
      Wi-Fi, LTO/CFI, ABI/KMI symbol list and module signing/loading.
- [ ] Build Image, all external .ko, dtb/dtbo, boot/vendor_boot/vendor_dlkm
      through matched tooling; compare modversions and KMI, inspect dmesg.
- [ ] Reproduce ghost touch on an actual mondrian, fix the **actual driver /
      power / firmware defect**, then test input suspend/resume, 60/120 Hz,
      multi-touch, charging, proximity, thermal and UDFPS.
- [ ] Establish Android 17 first release versus QPR1+ support policy.
- [ ] Test FBE, AVB/recovery/rollback, CTS/VTS and production signing
      separately from source-host checks.

**Do not** merge or run these prospective source changes merely to make a
kernel version look newer. Non-reviewed `vendor.lineage.*` dependencies
are excluded from the independent PE-Reborn platform. FM radio excluded.
