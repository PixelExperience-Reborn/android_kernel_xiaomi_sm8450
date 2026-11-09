# Official Qualcomm SDE/DSI source candidate for mondrian

Source: https://github.com/qualcomm-linux/display-driver
Pinned commit: `7b546db38822a40bc1beb5a9ace006b6541b947f`
Destination: `techpack/display` in the **isolated trial branch**.

- The original Xiaomi `drivers/gpu/drm/msm` DRM implementation is not
  deleted, modified or enabled by this source import.
- Qualcomm provides `config/gki_waipiodisp.conf` and `msm/Kbuild`.
- The display controller on SM8475/CAPE and the Xiaomi M11A panel
  still require exact matching DT, kernel ABI, firmware and HWC checks.
- This source snapshot is **not yet known to compile with Xiaomi 5.10.81**,
  to produce a valid `msm_drm.ko`, or to support AOSP 17 graphics HAL.
- Do not build both DRM providers into the same kernel or package both
  modules; select one verified target implementation.
- Original upstream LICENSE.txt, NOTICE and file-specific licenses
  have been retained. No vendor blobs are included.
- The Qualcomm code itself references other multimedia drivers/headers
  and version-dependent kernel APIs; validate these before integration.

This source trial cannot be merged into the production `seventeen`
branch until exact compile, API/ABI, display panel and boot tests pass.

## Source compatibility status — 2026-11-09

Official Qualcomm upstream branch `main` was pinned at
`7b546db38822a40bc1beb5a9ace006b6541b947f`.
Its source contains `msm/Kbuild` for `CONFIG_ARCH_WAIPIO=y`, and
`config/gki_waipiodisp.conf` declares the Qualcomm display module
build. The upstream display driver references additional `mm-drivers`
components. None has been copied or guessed here.

The older generic `drivers/gpu/drm/msm` already present in Xiaomi's
kernel has been deliberately preserved as-is. In the checked Xiaomi
`gki_defconfig` + `mondrian_GKI.config`, `CONFIG_DRM_MSM` is not
selected, and its older DPU/DSI catalog does not advertise SM8475/CAPE.

Before qualifying new Qualcomm sources for this handset, verify the
actual Linux 5.10 kernel APIs, `msm_drm.ko` build with matching
`Module.symvers`, required multimedia headers, a suitable M11A panel
DT, display power and DSI, recovery splash, UDFPS/HBM, hardware
composer and Android 17 graphics interfaces. Mere source import
cannot qualify these hardware paths.
