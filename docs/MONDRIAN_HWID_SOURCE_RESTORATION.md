# Mondrian hardware identification (HWID) — explicit missing OEM component

Device: **POCO F5 Pro / Redmi K60**, `mondrian`, M11A / SM8475.
Project base: independent PE-Reborn **AOSP 17**. Kernel base remains
**Xiaomi's original 5.10.81**, `MiCode/Xiaomi_Kernel_OpenSource`
`mondrian-s-oss@989b27aa8391a2ede9b067b53877c4c3343955fe`.

## Why this source restoration is necessary

The **official Xiaomi source itself** unconditionally contains
`source "drivers/misc/hwid/Kconfig"` in `drivers/misc/Kconfig`
and `obj-y += hwid/` in `drivers/misc/Makefile`, but fails to
publish the referenced `drivers/misc/hwid` directory. It cannot
finish the upstream `gki_defconfig` Kconfig parsing.

This is not an invitation to replace the kernel with the LF/LineageOS
baseline. The PE-Reborn kernel's entire remaining tree is OEM Xiaomi.

A **four-file** self-contained upstream-derived GPL-2.0 implementation
was restored from:
`LF52406/android_kernel_xiaomi_sm8450@283772ceb84491fd446e340fd211d45fb9dd9a36`
and independently inspected against the public LineageOS source.
Original copyright notices for Xiaomi (2021) and LineageOS (2022)
are preserved. Each original Git blob SHA was verified before copying:

| Path | Exact original source Git blob SHA |
| --- | --- |
| `drivers/misc/hwid/Kconfig` | `4ba57eef4e31dbad80ca518d4b3beacb07c90eb6` |
| `drivers/misc/hwid/Makefile` | `ef74e1ba40cc90d4082fa8ee8f75b75a1a89265c` |
| `drivers/misc/hwid/hwid.c` | `ff085f3647fc75e34a4edc39fd1b3a00a03b99e3` |
| `drivers/misc/hwid/hwid.h` | `3c0a1000395c0c17fd5a9e7b7be020bc0a3f1959` |

The header defines `HARDWARE_PROJECT_M11A = 14` for mondrian,
the exact hardware family required here. The driver provides module
parameters and exports hardware version helpers.

**This code is restored but is not yet declared operational**.
The original Xiaomi mondrian fragment already sets
`CONFIG_MI_HARDWARE_ID=m`; the missing source is required for that
device-selected module. The HWID Kconfig/driver is now present, and the
actual `olddefconfig` check verifies the module selection. Device
runtime, kernel ABI, Qualcomm modules and FOD still require separate
hardware validation; this does not prove a complete BSP or boot.

## Verification

Run the real OEM `gki_defconfig` and fragment `olddefconfig` again,
confirm source parsing passes, and separately verify EROFS/F2FS crypto
flags. If another unpublished Xiaomi source dependency is detected,
restore the minimal necessary component with exact provenance; do
not comment out Kconfig statements or silently remove device functions
to make CI green.


## Explicitly excluded OEM dangling PLAID reference

The Xiaomi `drivers/misc/Kconfig` also referenced an unpublished
`drivers/misc/plaid/Kconfig`, and `drivers/misc/Makefile` referenced
`CONFIG_XIAOMI_GPU_PLAID`. No Xiaomi OEM `mondrian_GKI.config`,
`mondrian_consolidate.config`, or GKI defconfig selects this
unpublished module. We removed the **two invalid integration entries**
with explanatory comments instead of making a fake driver or importing
an unrelated hardware service. This is not equivalent to disabling a
verified mondrian runtime component; reintegration requires original
source and evidence of real device support.

A real OEM `gki_defconfig` + mondrian fragment + `olddefconfig`
passed after restoring HWID and excluding the dangling PLAID
reference: https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/42596972649
