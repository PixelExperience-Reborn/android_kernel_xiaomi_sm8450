# PixelExperience-Reborn — original Xiaomi mondrian kernel source

**OEM authority:** https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/mondrian-s-oss  
**Immutable Xiaomi commit:** `989b27aa8391a2ede9b067b53877c4c3343955fe`  
**Git root tree:** `cc1d5e5fc0f576c3ba3a7a8497de53f6e6023dc8`  
**Device:** POCO F5 Pro / Redmi K60 (`mondrian`, Qualcomm SM8475).  
**Project:** PixelExperience-Reborn, independently developed for clean AOSP 17.

The full source snapshot is an attributed **Xiaomi OEM Linux 5.10.81
starting point**, not a finished Android 17 kernel. The Xiaomi release
is incomplete: matching external Qualcomm modules and DT/DTBO, touch
and fingerprint firmware, exact Common Kernel and KMI/toolchain may not
be present. Never invent missing files or declare a full bootable
kernel based only on an OEM source checkout.

The prior LF52406/LineageOS 5.10.269 tree was intentionally **not**
imported into this branch. Individual pieces may be evaluated later as
technical references, compared against Xiaomi's device-specific
implementation, and adapted as new reviewed commits with attribution.
Kernel-source reuse is distinct from inheriting a ROM platform/product.

Retain the original COPYING/LICENSES/SPDX notices; do not copy
proprietary binaries without appropriate rights. Production image,
external-module, DTBO, AOSP17 QPR/ABI, encryption and physical hardware
qualification remain pending. `seventeen` is unchanged.
