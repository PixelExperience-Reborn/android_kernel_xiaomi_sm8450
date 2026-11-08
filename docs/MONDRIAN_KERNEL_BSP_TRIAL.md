# PixelExperience-Reborn AOSP 17 — mondrian kernel BSP qualification

Date: **2026-11-08**. Scope: POCO F5 Pro / Redmi K60 (`mondrian`, SM8475).
**This is a working-source trial, NOT a buildable shipping kernel or Android17 QPR1+ port.**

## Actual source progress

The existing PE kernel repository originally held only audit contracts.
`lf52406-bsp-trial-lock.json` now locks an **actual candidate source trio**
with independent full Git commit/root-tree IDs and **13 pinned file blobs**:

| Role | Public source trial | Immutable commit |
| --- | --- | --- |
| Linux kernel, v5.10.269 | `LF52406/android_kernel_xiaomi_sm8450` | `283772ceb84491fd446e340fd211d45fb9dd9a36` |
| Qualcomm external modules | `LF52406/android_kernel_xiaomi_sm8450-modules` | `91cdb1347970ae98291986926eb16bf1b172138e` |
| Qualcomm and mondrian DT/DTBO | `LF52406/android_kernel_xiaomi_sm8450-devicetrees` | `99f1330d8dce0c80de5a19f425d0a118b2eb7fe3` |

This does **not** claim that all external modules are compatible with
the kernel or that LF24's source trees become the PixelExperience ROM base.
A clean AOSP 17 build remains independent; the LF repos supply
hardware *trial sources*, not a ROM product or permanent build dependency.
No code has been copied into PE's audit-only kernel branch yet.

Two real GitHub Actions checks are distinct:

- `tools/verify_lf_bsp_triplet.py --online` verifies immutable Git
  commits, root Git trees, exact Git blobs and textual source constraints.
- `tools/verify_trial_workspace.py` validates physical sparse checkout
  paths and pinned commit/tree/blob identity plus Kconfig/KMI inputs.
- `tools/try_mondrian_kconfig.sh` generates a real `.config` using the
  full kernel source and all five fragments as a **host-only smoke test**.
  This does not compile Image/DTBO/Qualcomm modules or validate its kernel
  ABI, but detects incompatible or ignored Kconfig symbols early.

## Standalone build and ROM packaging are NOT the same

`build.config.msm.waipio` references a **distinct Android Common Kernel
checkout at `common/`** and uses `msm-kernel/` for Qualcomm sources,
`external/dtc/` for DTC, and `build/android/` tools for DTB assembly.
It declares `BOOT_IMAGE_HEADER_VERSION=3`.

The reference ROM board instead uses `BOARD_BOOT_HEADER_VERSION=4`.
**This is not proof that either source is wrong:** a standalone Qualcomm
build and Android product `mkbootimg` may package images differently.
Resolve against real mondrian `boot` and `vendor_boot` partition
headers, ramdisk fragments, bootconfig, AOSP17 build rules, and AVB first.
Never blindly set both to the same value to suppress a build warning.

The source config stack for a direct device-kernel trial is:

```text
gki_defconfig
vendor/waipio_GKI.config
vendor/xiaomi_GKI.config
vendor/mondrian_GKI.config
vendor/debugfs.config
```

`waipio_GKI.config` enables CAPE/WAIPIO, which means the shared kernel
also retains board support for other Qualcomm products. **Do not include
their DTBOs in the mondrian product image** by default. Verify:
- touch `goodix,gt9916S` with matching Goodix SPI driver, firmware and ESD;
- separate `goodix,fingerprint` kernel/HAL/TEE path;
- M11A display overlay and required HBM/FOD state;
- cape/cape-v2/capep base DTBs and PM8008 mondrian board overlay;
- camera sensor overlay, video pipeline, WLAN, NFC and storage;
- first-stage and second-stage module sets with actual KMI/CRC and
  `vendor_dlkm` source-built artifacts.

External Qualcomm module `Kbuild` contains device-sensitive
`CONFIG_TARGET_PRODUCT_MONDRIAN` logic. The original OEM module
list repeats two watchdog entries; do not use it as a final
`modules.load` without validating aliases and hard dependencies.
The historical generic source also contains FM-related modules. They
must remain excluded from PE's target product; never automatically
enable FM radio apps, JNI, HAL or services.

## Opt-in source checkout in our own manifest

The **separate** manifest Draft PR #3 contains
`aosp17_pe_mondrian_bsp_trial.xml`, which preserves the independently
written `device/xiaomi/mondrian` and `sm8450-common` product trees and
temporarily replaces **only the three audit-only kernel paths** with
the three immutable LF source-trial revisions:

```bash
repo init -u https://github.com/PixelExperience-Reborn/manifest \
  -b bringup/a17-mondrian-audit-profile-20261108 \
  -m aosp17_pe_mondrian_bsp_trial.xml

repo sync -c -j4 \
  device/xiaomi/mondrian device/xiaomi/sm8450-common \
  kernel/xiaomi/sm8450 kernel/xiaomi/sm8450-modules \
  kernel/xiaomi/sm8450-devicetrees vendor/aosp

python3 .repo/manifests/tools/verify_mondrian_bsp_checkout.py --root .
```

This permits real kernel source inspection within an AOSP17 tree **without
merging** the reference ROM's device products or frameworks. It is not a
production manifest. Pin a known-good ACK 5.10 commit, matching LLVM,
DTC, KMI symbol list and build scripts **before** starting full compilation.
The source-trial lock deliberately leaves these versions unset.

## Release-blocking qualification stages

1. Real kernel config & compiler with reproducible toolchain and
   symbol ABI; no unsupported or silently dropped flags.
2. Compile `Image`, vmlinux, `Module.symvers`, all required Qualcomm
   external modules and Mondrian DTB/DTBO. Compare KMI CRCs and
   `modinfo` vermagic/dependencies across the exact build.
3. Run `fdtoverlay` for every compatible CAPE base and every overlay;
   verify physical board IDs, display, camera, touch and fingerprint.
4. Package correct `boot`, `vendor_boot`, `vendor_dlkm`, `dtbo`
   and recovery with qualified fstab, KeyMint/FBE, AVB signing and
   rollback indexes. Test target-files and OTA A/B partition handling.
5. Flash **only after** the above to a test mondrian; verify boot,
   touchscreen, UDFPS, radio/IMS, Wi-Fi, cameras, storage, sensors,
   charging, sleep/resume and recovery decryption; validate CTS/VTS.

**Android 17 kernel policy:** the current AOSP matrix includes GKI 5.10
for initial Android 17, explicitly **NOT Android 17 QPR1 and later**.
Thus this 5.10.269 candidate is a possible bring-up and diagnostic path,
not a finished modern Android 17 long-term solution. A future supported
5.15/6.1 port requires new coherent SoC kernel, modules and DT, not merely
changing `SUBLEVEL`.

References:
- https://source.android.com/docs/core/architecture/kernel/android-common
- https://source.android.com/docs/core/architecture/kernel/stable-kmi
- https://source.android.com/docs/core/architecture/partitions/vendor-odm-dlkm-partition
- https://source.android.com/docs/core/architecture/partitions/vendor-boot-partitions

**Do not merge this audit PR into production `seventeen` merely because
the Git SHA, sparse source or host Kconfig CI passes.**
