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

## Xiaomi's own published mi_disp source as reference (not a mondrian import)

A manufacturer-maintained independent reference now exists:
[MiCode/vendor_opensource_display-drivers, bsp-vermeer-t-oss](https://github.com/MiCode/vendor_opensource_display-drivers/tree/bsp-vermeer-t-oss) at immutable commit `c696b28150245a9ddd1f2701f071e4b580b44ce2`.
Its `msm/mi_disp/mi_disp_lhbm.c` and `msm/mi_disp/mi_disp_feature.c` implement Xiaomi LHBM/FOD and event handling, while `include/uapi/display/drm/mi_disp.h` defines the Xiaomi userspace ioctl ABI. This manufacturer source is **not for mondrian** and does **not** establish matching panel values, board revision, module KMI or working AOSP 17 HAL.

The source-only [mondrian Xiaomi Display comparison workflow](../.github/workflows/mondrian-xiaomi-display-candidate.yml) checks the immutable manufacturer revision and Git blob hashes, compares the selected Qualcomm source and emits an explicit **BLOCKED** record. It rejects any silent partial Xiaomi-ABI import until reviewed requalification. No blobs, DTS, DCS sequences or LineageOS source have been copied to our device. Continue only with a native mondrian adaptation and physical Xiaomi-stock panel evidence. Existing triple-root compiled OEM+Qualcomm Display remains the only qualified binary milestone.

The OEM comparison found a critical ABI ownership detail: the manufacturer
`LOCAL_HBM_UI_READY` and `FOD_LOW_BRIGHTNESS_CAPTURE` bits are defined in
`msm/mi_disp/mi_disp_lhbm.h` (kernel-internal), whereas ioctl/event names
are in its separate UAPI `mi_disp.h`. A native AOSP17 fingerprint service
must not assume another ROM's header layout; verify the numeric contract
against the actual selected kernel before implementing userspace events.

## Fail-closed Qualcomm DSC parser hardening (OEM 5.10.81)

The selected Qualcomm parser previously rejected a zero slice height but
**allowed height 1**, even though `sde_dsc_populate_dsc_config()` divides by
`slice_height - 1`. The native PE-Reborn patch validates height >= 2 and
height <= picture height before invoking that function. It also checks the
16-bit PPS picture dimensions and the 10-bit fixed-point PPS bpp integer
range before encoding. This affects only malformed DSC configurations;
the 1440x3200, slice-height 32 candidate observed in third-party diagnostics
would not be rejected on these grounds. No candidate is approved without
independent manufacturer evidence.

The source regression tests and full OEM/Display/MMRM compile gate must both
pass at the new kernel commit before updating pinned external module and
devicetree checks. `seventeen` and production panel selection remain unchanged.

## 16 Nov 2026 — Native mondrian LHBM/FOD state model (inert hardware boundary)

The native PixelExperience-Reborn C state model compiles into Qualcomm WAIPIO
msm_drm.ko as msm/mondrian/mondrian_lhbm_fsm.o. It is an internal implementation
component only: no DSI writes, sysfs, ioctl, exported symbol, fake device node,
Goodix callbacks or user-facing interface have been created.

State transitions are: qualified panel ON -> IDLE -> fingerprint DOWN ->
STARTING and an ON intent -> actual hardware acknowledgement -> READY
event -> fingerprint UP -> OFF intent -> actual hardware acknowledgement ->
IDLE. Doze and finger cancellation invalidate pending ON operations and
request a compensating OFF; panel OFF and ESD immediately revoke FOD ready
and invalidate stale acknowledgements without sending unsafe DSI commands.
Timeouts and failed OFF requests become a sticky fault until full panel reset.
Generational tokens reject stale acknowledgements and fail on integer wrap.
All transitions must be serialized by the future panel lock owner.

The native C regression suite (11 scenarios) executes on a host compiler
first, followed by the real pinned LLVM23 OEM 5.10.81/Qualcomm Display
build to qualify msm_drm.ko and ABI. The explicit factory-qualification flag
is false in production because there is currently no instantiating caller.
Host tests simulate qualification purely to test transitions; they do
NOT assert the real M11A/R66451 panel is qualified. Never create a false
FOD-ready event before the actual DSI operation has been verified.

Next gate: authenticated Xiaomi stock DTBO/vendor_boot, exact panel-specific
LHBM commands, synchronized DSI hardware implementation with safe ACK/error
path, AOSP 17 biometric/UDFPS service and SELinux/VINTF contracts, and
physical mondrian tests of doze, ESD, thermals and fingerprint operation.
Do not merge seventeen or enable production DTBO/LHBM from this milestone.

Additional safety refinement: in-flight ON cancellation is deferred until
its actual completion/ACK; an OFF intent must never overtake an unresolved
ON transaction. A timed-out ON is treated as a required full-panel reset,
not a potentially racing OFF DSI write. Duplicate PANEL_ON cannot bypass
Doze. This behavior is host-tested before eventual hardware adaptation.

## 16 Nov 2026 — inert lifecycle wiring to the actual Qualcomm DSI panel

The `mondrian_lhbm_fsm` is now embedded per `struct dsi_panel` for
`CONFIG_ARCH_WAIPIO`. `dsi_panel_get()` initializes it with
`factory_qualified=false` unconditionally. Native `dsi_panel_enable()`
records panel ON *after successful DSI ON* under `panel_lock`; the
disable path invalidates FOD before DSI OFF or ESD handling, and full
power-down reinforces OFF. LP1/LP2/NOLP events are recorded only after
successful panel commands, also under `panel_lock`. This uses the native
Qualcomm panel lifetime, not another ROM's device abstraction. The bridge
discards any unintended hardware intent and resets the factory qualifier
instead of issuing unknown DCS or reporting a fake fingerprint-ready event.

The added source/locking regression suite and LLVM23 `msm_drm.ko` compile
must pass before the new exact SHA can be pinned into Modules/Devicetrees.
This is lifecycle observability only: continuous splash and external
DRM-panel/bridge paths, real LHBM DSI commands, `mi_disp` UAPI, AOSP17
Goodix HAL/SELinux/VINTF and physical tests remain unqualified. Do not
activate fingerprint illumination from this code.
