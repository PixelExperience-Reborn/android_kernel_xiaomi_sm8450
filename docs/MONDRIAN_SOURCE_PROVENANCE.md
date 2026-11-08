# PixelExperience-Reborn — mondrian kernel source provenance

**Device:** POCO F5 Pro / Redmi K60 (`mondrian`, physical Qualcomm SM8475, taro/CAPE family).  
**Platform goal:** independent PixelExperience-Reborn on clean AOSP 17.  
**Kernel source presently imported:** Linux 5.10.269.

## Actual source import

- Full kernel source snapshot derived from
  [LF52406/android_kernel_xiaomi_sm8450](https://github.com/LF52406/android_kernel_xiaomi_sm8450)
  at the **immutable source commit** `283772ceb84491fd446e340fd211d45fb9dd9a36`.
- Source commit Git tree: `a621bf4b1939281af398ef5248e86222a9bfdfa3`.
- PE-Reborn initial source import commit: `e1d05dc9f1cecd67b6e11bd25fb87b80947577fc`.
- Import GitHub Actions run:
  https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/42493390489
- The importer verified **68,756 upstream tracked files** and copied the
  complete checkout while preserving symbolic links. Twelve critical
  imported files were compared against their original Git blob SHA.
- This is an explicitly attributed **snapshot**, not a claim to have
  transferred or rewritten the entire historical Git commit graph.
  Upstream history remains available in LF52406.

## Official Xiaomi OEM reference — incomplete, but required

- [MiCode/Xiaomi_Kernel_OpenSource, branch mondrian-s-oss](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/mondrian-s-oss)
- OEM source commit: `989b27aa8391a2ede9b067b53877c4c3343955fe`.
- OEM source Git tree: `cc1d5e5fc0f576c3ba3a7a8497de53f6e6023dc8`.
- Public OEM source references an older 5.10.81 kernel and does **not**
  provide every downstream component required for a complete modern
  Android 17 ROM. Use OEM files as evidence for actual mondrian hardware
  configuration, device-specific deviations and license provenance;
  do not assume that dropping the OEM tree in place produces a bootable
  5.10.269 kernel.

Important hardware checks to preserve: Goodix touchscreen with
`goodix,gt9916S` DT compatible versus upstream `goodix,brl-d`;
separate `goodix,fingerprint` and associated HAL/TEE; M11A display,
CAPE variants, PM8008, sensor camera DTBO, WCNSS/Wi-Fi, charging and
recovery/encrypted storage.

## Rights and independence

Keep the GPL-2.0 and other SPDX/file-specific license notices in the
imported kernel. The source-tree attribution does not authorize
proprietary firmware redistribution without separate rights.

This is the **PE-Reborn kernel source** branch, not a transplanted
LineageOS product or Android platform. All new device build rules must
use PE-Reborn's own `vendor/aosp` and AOSP 17.

The kernel still requires **matching external Qualcomm modules,
DT/DTBO, Android Common Kernel/toolchain qualification, KMI/Module.symvers,
vendor firmware, first-stage boot, FBE/KeyMint, AVB**, and an actual
target build. Linux 5.10.269 source presence is not proof of QPR
compatibility or a bootable `boot.img`.

## Branch policy

This full source exists on
`bringup/a17-mondrian-kernel-full-source-20261108`.
The default `seventeen` remains protected from unqualified imports.
Promote source into `seventeen` only following source audit, build
and device-specific acceptance.
