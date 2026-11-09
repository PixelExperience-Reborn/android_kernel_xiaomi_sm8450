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

**This code is restored but is not yet declared operational**:
`CONFIG_MI_HARDWARE_ID` remains disabled/unselected in the stock
OEM mondrian fragment pending dependency and device tests. OEM
Kernel/DT/firmware interfaces, Qualcomm modules, and FOD still require
a separate compatibility audit. The restored HWID files are not
equivalent to a complete Qualcomm BSP or a successful physical boot.

## Verification

Run the real OEM `gki_defconfig` and fragment `olddefconfig` again,
confirm source parsing passes, and separately verify EROFS/F2FS crypto
flags. If another unpublished Xiaomi source dependency is detected,
restore the minimal necessary component with exact provenance; do
not comment out Kconfig statements or silently remove device functions
to make CI green.
