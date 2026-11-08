# PE-Reborn AOSP 17 / mondrian — provisional BSP dependency contract

State: **BLOCKED / NOT BUILDABLE**. This is a source-integration design and
evidence set, not a completed kernel or a device tree import. Only physical
POCO F5 Pro / Redmi K60 (`mondrian`, SM8475) is in scope.

## Build graph (all source selections are currently NULL)

```text
AOSP 17 product (independent PE-Reborn)
  device/xiaomi/mondrian  -> device/xiaomi/sm8450-common
          |                         |
          +--> kernel/xiaomi/sm8450 +++ exact kernel config/KMI/toolchain
                        |                 |
                        +--> kernel/xiaomi/sm8450-modules
                        +--> kernel/xiaomi/sm8450-devicetrees
                        |           |- cape base DTB + mondrian PM8008 overlay
                        |           |- M11A display overlay
                        |           |- mondrian camera-sensor overlay
                        +--> vendor/xiaomi/{mondrian,sm8450-common}
                                  |- vendor firmware / HAL / signed proprietary binaries
                                  |- boot, vendor_boot, vendor_dlkm and related partition contracts
```

The diagram shows **required interfaces**, not permission to clone LineageOS
into PE-Reborn. Kernel/modules/DT/firmware must be assembled from provenance-
reviewed, mutually compatible sources. GPL source can be studied subject
to its notices; proprietary vendor blobs and firmware have separate
redistribution and security constraints. Never auto-import a ROM's
`vendor.lineage.*`, `lineage_*` make product, or FM radio components.

## P0: kernel and external module coupling

- Xiaomi OEM `mondrian-s-oss` declares Linux **5.10.81** and sources
  `common/build.config.common`, `common/build.config.aarch64`,
  `build.config.msm.common` and `build.config.msm.gki`. It also sets
  `BUILD_VENDOR_DLKM=1` and `MODULES_LIST_ORDER="1"`. The complete build
  workspace must resolve those files, `msm-kernel`, supported Clang/LLVM,
  `KERNEL_DIR`, final `.config` and separate module source roots.
- The later public 5.10.269 kernel and Qualcomm module repository are
  **read-only compatibility references**, not an approved PE branch pair.
  A matching kernel version string cannot prove matching `Module.symvers`,
  exported GKI KMI, `CONFIG_MODVERSIONS`, LTO/CFI, vmlinux BTF, module
  signing, module load ordering or `vendor_dlkm` packaging.
- OEM `modules.list.msm.mondrian`: 106 ordered entries, 104 distinct names,
  two repeated (`gh_virt_wdt.ko` and `qcom_wdt_core.ko`). Preserve
  original evidence. Classify built-in versus modules, `modules.load` vs
  `modules.load.recovery`/`vendor_boot` and `vendor_dlkm`, required
  firmware, aliases and soft dependencies **before** generating a new list.
- The reference external module tree has a product-sensitive audio `Kbuild`
  defining `CONFIG_TARGET_PRODUCT_MONDRIAN`; do not assume the same module
  bits work with all targets or that a generic sm8450 manifest covers SM8475.

**Release gate:** only select a matched kernel+modules commit/defconfig/
toolchain/boot image layout after a successful full build and symbol/ABI
audit, followed by a device boot and storage/network/display tests.

## P0: mondrian-specific DT/DTBO coupling

The inspected `lineage-24.0` sources are evidence of *possible*
platform-specific wiring, not necessarily current on-device hardware
identification or a validated PE DT set:

| Layer | Inspected file | Required qualification |
| --- | --- | --- |
| Qualcomm base | `qcom/Makefile` | `mondrian-sm8475-pm8008-overlay.dtbo` bases: `cape.dtb`, `cape-v2.dtb`, `capep.dtb`; check bootloader board/SoC revisions and selected overlay order |
| Mondrian DTS | `qcom/mondrian-sm8475.dtsi` | Includes `mondrian-pinctrl.dtsi` and `xiaomi-sm8475-common.dtsi`; resolve entire include graph and compatible/board-id |
| Touch | `qcom/mondrian-sm8475.dtsi` | Goodix GT9916S over SPI at **15 MHz** in reference; IRQ GPIO 21, reset GPIO 20 and regulator constraints are unverified on this phone |
| Screen | `qcom/display/display/mondrian-sde-display-mtp.dtsi` and `qcom/display/Kbuild` | M11A DSC command panel and `mondrian-sde-display-mtp-overlay.dtbo`; verify physical panel ID and refresh, HBM/FOD, 60/120 Hz |
| Camera | `qcom/camera/config/waipio.mk` | `mondrian-sm8475-camera-sensor.dtbo` and matched modules/sensor vendor HAL; don't mix board revisions |
| Fingerprint | `qcom/mondrian-sm8475.dtsi` | Independent `goodix,fingerprint` node; TEE/KeyMint/biometrics HAL and HBM/FOD interaction must be qualified |

**Release gate:** dtc compile; `fdtoverlay` apply to all supported base
DTBs; check bootloader identity, reserved memory/IOMMU regulators/clock
phandles, and exact compiled DTB/DTBO artifacts. Matching file names
alone are insufficient.

## P0: Goodix Berlin SPI ghost-touch investigation

Manufacturer `goodix/goodix_ts_berlin:goodix_brl_spi.c` at pinned commit
`6c4b81587d43cf4ebf59cc63fe2916d77e4e8ce2` matches
`goodix,brl-d`, whereas the inspected mondrian DTS and newer Qualcomm
SPI driver use `goodix,gt9916S`. This **is a real of_match difference**.

Do not edit the compatible string alone or install a generic driver without
first reconciling: actual IC revision/PID, firmware and config
(`goodix_firmware_m11a.bin`, `goodix_cfg_group_m11a.bin`),
power/reset/IRQ polarity, ESD recovery, special Xiaomi touch mode hooks,
input protocol and events, screen-off and charger behavior. The DTS's
`goodix,panel-max-x = <14400>` / `panel-max-y = <32000>` must not be
silently interpreted as Android logical display pixels (1440x3200):
validate event coordinate scaling and firmware units on device.

The reference fingerprint node is a **different driver path** from
Goodix touch. No UDFPS acceptance until enroll/auth/cancel, lockscreen and
screen-off FOD, panel illumination and touch interactions are tested
together. Source-only tests cannot diagnose or fix phantom touches.

## Android 17 platform lifetime decision

AOSP documents GKI `android12-5.10` and `android13-5.10` for initial
Android 17 **only**, excluding Android 17 **QPR1+**.
Source: https://source.android.com/docs/core/architecture/kernel/android-common

Treat 5.10 as a bring-up *candidate* with an explicit release limit,
not as a guaranteed supported long-term Android 17 foundation.
Moving to 5.15/6.1/6.6 is a coordinated hardware port requiring a new
compatible kernel, vendor modules, DT, firmware and platform policy.
Do not claim QPR support solely by setting `SUBLEVEL` higher.

## Verification commands

```bash
# Offline GitHub PR tests: checks contract metadata, NOT public source contents.
python3 -m unittest discover -s tests -v

# Read-only: verify pinned source commit/tree IDs and exact file Git blob SHA.
python3 tools/verify_public_evidence.py --online
```

The checked inputs are machine-readable in `source-candidates.json` and
`reference-evidence.json`, and consist of 5 pinned public commits and
11 pinned individual blobs. No kernel sources, external modules, DTBO,
firmware or production signing keys have been imported by this audit.

### Required next implementation phase

1. Pin a **single buildable BSP bill of materials** (source and binary
   provenance, license and a locked manifest) including all child repositories.
2. Reconstruct OEM/QCOM build configuration and capture reproducible tool
   versions, output module list, DTBO and ELF/KMI reports in CI.
3. Review Goodix and M11A code paths; prepare small driver/DT adaptation
   as its own review, then run in-device touch/UDFPS acceptance.
4. Confirm AOSP 17 release/QPR kernel policy and integrate the **tested**
   kernel BSP into our own `pe_mondrian` product; retain clean AOSP platform.

**Explicitly unproven:** a successful kernel build, Android Soong parse,
vendor binary compatibility, image signing, physical boot, UDFPS,
camera operation, touch reliability and QPR1+ platform compatibility.
