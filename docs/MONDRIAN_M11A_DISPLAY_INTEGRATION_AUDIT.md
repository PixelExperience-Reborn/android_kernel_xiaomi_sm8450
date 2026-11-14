# mondrian M11A panel integration gate — PixelExperience-Reborn AOSP 17

Status: **Display module compile/ABI PASS; panel hardware integration BLOCKED** (14 Nov 2026).

## Exact tested source combination

- OEM kernel: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450@2466406b9beac724960b0c88e6e794421d0466e7` (Xiaomi OEM 5.10.81).
- Qualcomm WAIPIO SDE/DSI: pinned official snapshot `7b546db38822a40bc1beb5a9ace006b6541b947f`, with the adaptations isolated in [Display PR #4](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/pull/4).
- Modules/MMRM: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules@95b795b6167bc83c1b3fa5d68f85b0906808c51c` (diagnostic build).
- OEM DTS: `PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees@38e6cd7e65554f898e117dc099cec17a27930602` (diagnostic Cape/mondrian base + Goodix).
- [Actual full build #43604810776](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/43604810776): `msm_drm.ko` compiled and passed MODPOST/`vermagic` against pinned OEM `Module.symvers`; **not a hardware boot**.

## Manufacturer-first M11A data contract

**Implementation source policy:** only original Xiaomi MiCode source, the matching Xiaomi **stock firmware/DTBO for mondrian**, and appropriate official Qualcomm APIs are acceptable implementation inputs. LineageOS and other ROMs may be used to understand the problem, **never as a source of copied DTS, values, power commands, drivers or code**. A tested Qualcomm `msm_drm.ko` is not evidence of a complete M11A panel.

The public Xiaomi `mondrian-s-oss` DTS subset contains the board overlay and regulators but **not** the complete M11A panel configuration. Before selecting a panel for PixelExperience-Reborn AOSP 17, acquire OEM evidence for:

| Hardware area | Required Xiaomi-authored or Xiaomi-stock evidence | Current verified state |
|---|---|---|
| Exact panel and revision | Matching stock DT/firmware panel identity, SKU and board-id | Missing from published OEM DTS subset |
| Command mode, timings and DSC | Exact stock panel timing modes, PHY rates, DSC revision, slice sizes and initialization sequences | Qualcomm parser and DSC code build; no manufacturer panel DTS qualified |
| Regulators and reset | Xiaomi stock supply topology, voltage, enable/reset order and ESD status path | Selected OEM Cape regulators exist; panel wiring unqualified |
| OLED brightness/Doze | Matching stock DCS command sequences and thermal/ESD recovery | Not available as reviewed OEM source yet |
| Goodix UDFPS with LHBM | Device-verified Xiaomi panel illumination/FOD protocol and biometric HAL contract | OEM Goodix GPIO/regulator contract checked; display coordination unqualified |

Native recovery plan: [Devicetrees OEM stock-DTBO diagnostic](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees/blob/bringup/a17-mondrian-oem-bsp-20261111/docs/XIAOMI_M11A_OEM_SOURCE_RECOVERY.md). Diagnostic extraction does not automatically certify source authenticity or authorize production integration.

## Verified boundary between diagnostic build and release

1. Preserve OEM source provenance. The selected Xiaomi `mondrian-s-oss` branch lacks a complete manufacturer M11A panel description at the inspected paths. Use the Xiaomi official fastboot firmware or device-owned stock partition as the reference for independently engineered hardware parameters. Do **not** substitute LineageOS sources, invent panel DCS power tables or claim binary-derived evidence automatically proves authorship.
2. Obtain a validated Xiaomi M11A panel DTS / matching OEM firmware source (or an independently reimplemented, device-verified equivalent), match actual panel SKU and board IDs, compile with our three Cape bases and mondrian overlay, verify `fdtoverlay` and all `#include` dependencies. This hardware source gate is **not complete**.
3. Audit and implement the required **Xiaomi-local** LHBM/FOD transitions, brightness and gamma mapping in our selected Qualcomm DSI hardware path, maintaining compatibility with Goodix UDFPS, panel power, ESD, suspend/resume and Android 17 biometric interfaces. Do not claim stock Qualcomm parsing provides Xiaomi features absent from its source.
4. Check DSC config and 60/90/120 modes against the actual panel data; assert no invalid slice dimensions/clock/refresh selections; qualify M11A with the exact AOSP 17 HWC/VINTF/SELinux and firmware combination.
5. Qualify real module load ordering and `vendor_boot`/`vendor_dlkm`, then validate boot, panel detection, ESD, off/on/doze, fingerprint illumination, refresh switching and thermal behavior **on mondrian hardware**. CI compile cannot establish runtime functionality.

## Stage isolation

Camera, Video and Audio remain explicitly out of scope. The AOSP 17 `seventeen` branch, ROM manifest and product module packaging must not be changed on the strength of a diagnostic Display build. OEM kernel Linux 5.10.269 upgrade requires its own complete ABI requalification.

### Related reviewed change

DSC parser rejects zero `qcom,mdss-dsc-slice-width` and `qcom,mdss-dsc-slice-height` before using the slice width as divisor: [commit `3cddcfe`](https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/commit/3cddcfea64ef7cec109fae428c27957d3d3c97bb). This prevents invalid DTS data from causing a division-by-zero; it does not supply a missing OEM panel definition.
