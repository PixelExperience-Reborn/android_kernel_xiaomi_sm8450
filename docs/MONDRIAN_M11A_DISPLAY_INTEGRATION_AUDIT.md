# mondrian M11A panel integration gate — PixelExperience-Reborn AOSP 17

Status: **Display module compile/ABI PASS; panel hardware integration BLOCKED** (14 Nov 2026).

## Exact tested source combination

- OEM kernel: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450@2466406b9beac724960b0c88e6e794421d0466e7` (Xiaomi OEM 5.10.81).
- Qualcomm WAIPIO SDE/DSI: pinned official snapshot `7b546db38822a40bc1beb5a9ace006b6541b947f`, with the adaptations isolated in [Display PR #4](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/pull/4).
- Modules/MMRM: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules@95b795b6167bc83c1b3fa5d68f85b0906808c51c` (diagnostic build).
- OEM DTS: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees@38e6cd7e65554f898e117dc099cec17a27930602` (diagnostic Cape/mondrian base + Goodix).
- [Actual full build #43604810776](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/43604810776): `msm_drm.ko` compiled and passed MODPOST/`vermagic` against pinned OEM `Module.symvers`; **not a hardware boot**.

## Read-only hardware facts requiring OEM confirmation

Reference for analysis **only**, not copied as our device tree: [official LineageOS mondrian panel description at `2e649a7`](https://github.com/LineageOS/android_kernel_xiaomi_sm8450-devicetrees/blob/2e649a7f3e762903eedad43d8256b91e28b512d8/qcom/display/display/dsi-panel-m11a-42-02-0a-dsc-cmd.dtsi), plus [board/display wiring](https://github.com/LineageOS/android_kernel_xiaomi_sm8450-devicetrees/blob/2e649a7f3e762903eedad43d8256b91e28b512d8/qcom/display/display/mondrian-sde-display-mtp.dtsi). Values must be validated against actual Xiaomi firmware/panel revision before our product selects them.

| Signal / mode | Read-only reference | Current PE-Reborn source readiness |
|---|---|---|
| Active display | 1440×3200, command mode, 60/90/120 Hz | Qualcomm DSI mode parser exists; no approved M11A product DTS |
| Compression | DSC 1.2 (`0x12`), slice 720×32, 2 slices/packet, 10 bits/component, 8 bits/pixel | Qualcomm DSC parser accepts v1.2 and these property keys. Zero slice dimensions now rejected before division. No actual panel mode build |
| Panel power | `vddio` 1.8 V, `vddd` 1.07 V, `vci` 3.0 V | Must map to selected OEM regulators and validate sequencing/board SKU |
| Panel ESD | Reference IRQ GPIO 116 and panel-specific ESD commands | Driver, DT pinmux and actual ESD recovery not qualified |
| UDFPS / local HBM | Xiaomi `mi,local-hbm-enabled`, FOD thresholds, DCS sequences and gamma selection | Current Qualcomm DSI parser has **no matching Xiaomi `mi,local-hbm`/FOD parsing**. No proven LHBM/UI-ready handshake |
| Touch vs fingerprint | OEM touch IRQ/reset GPIO 21/20; Goodix UDFPS IRQ/reset GPIO 40/41, 3.2 V L9C | Goodix static DT/binding checks passed; panel brightness/FOD coordination and firmware/HAL remain unverified |

## Verified boundary between diagnostic build and release

1. Preserve OEM source provenance. Xiaomi's [missing display tree report](https://github.com/MiCode/kernel_devicetree/issues/31) and [kernel component disclosure report](https://github.com/MiCode/kernel_devicetree/issues/37) explain why the selected OEM subset is not itself sufficient proof of a production M11A panel overlay. Do **not** substitute or bulk-copy Lineage trees or invent panel DCS power tables.
2. Obtain a validated Xiaomi M11A panel DTS / matching OEM firmware source (or an independently reimplemented, device-verified equivalent), match actual panel SKU and board IDs, compile with our three Cape bases and mondrian overlay, verify `fdtoverlay` and all `#include` dependencies. This hardware source gate is **not complete**.
3. Audit and implement the required **Xiaomi-local** LHBM/FOD transitions, brightness and gamma mapping in our selected Qualcomm DSI hardware path, maintaining compatibility with Goodix UDFPS, panel power, ESD, suspend/resume and Android 17 biometric interfaces. Do not claim stock Qualcomm parsing provides Xiaomi features absent from its source.
4. Check DSC config and 60/90/120 modes against the actual panel data; assert no invalid slice dimensions/clock/refresh selections; qualify M11A with the exact AOSP 17 HWC/VINTF/SELinux and firmware combination.
5. Qualify real module load ordering and `vendor_boot`/`vendor_dlkm`, then validate boot, panel detection, ESD, off/on/doze, fingerprint illumination, refresh switching and thermal behavior **on mondrian hardware**. CI compile cannot establish runtime functionality.

## Stage isolation

Camera, Video and Audio remain explicitly out of scope. The AOSP 17 `seventeen` branch, ROM manifest and product module packaging must not be changed on the strength of a diagnostic Display build. OEM kernel Linux 5.10.269 upgrade requires its own complete ABI requalification.

### Related reviewed change

DSC parser rejects zero `qcom,mdss-dsc-slice-width` and `qcom,mdss-dsc-slice-height` before using the slice width as divisor: [commit `3cddcfe`](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/commit/3cddcfea64ef7cec109fae428c27957d3d3c97bb). This prevents invalid DTS data from causing a division-by-zero; it does not supply a missing OEM panel definition.
