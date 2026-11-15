# PE-Reborn AOSP 17 — Xiaomi mondrian OEM Linux 5.10.81 hardware gate

Status: **OPEN / DIAGNOSTIC ONLY / DO NOT SHIP**

## Scope and source-of-truth

This is solely the kernel-BSP set for POCO F5 Pro / Redmi K60 (SM8475,
mondrian), not a completed PixelExperience-Reborn ROM:

- Xiaomi OEM kernel: PixelExperience-Reborn/android_kernel_xiaomi_sm8450
  pinned OEM commit 2466406b9beac724960b0c88e6e794421d0466e7
  (Linux **5.10.81**).
- Qualcomm Display trial: kernel PR #4, head
  e264bdd6c99d09b56da12febc61b0bc0daf59f44.
- External Modules: PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules
  PR #2, head 95b795b6167bc83c1b3fa5d68f85b0906808c51c.
- Devicetrees: PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees
  PR #2, head a7c1a5cf190e345a02b59818e211fd4338e20ce1.

**Freeze the kernel baseline at 5.10.81 for this qualification step.**
Do not bump the Makefile version, import a foreign kernel base, remove OEM
features to bypass compile errors, update the release manifest, or merge the
draft PRs. Linux 5.10.269 is a separately gated future choice, not an
immediate substitute for getting the current OEM hardware working.

Allowed sources are manufacturer Xiaomi OEM and qualified official Qualcomm
sources, with individually reviewed AOSP interfaces. LineageOS and other ROM
sources may inform investigation but must not be copied as the implementation.

## Verified today by actual CI (SOURCE/BUILD, not physical hardware)

1. OEM Xiaomi kernel compiled vmlinux, arm64 Image, selected in-tree modules
   and exact Module.symvers using Android LLVM 23. Reference:
   https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/42799538789
2. Qualcomm WAIPIO external msm_drm.ko compiled against the exact same OEM
   Module.symvers, with official MMRM and no duplicate DRM driver.
   Reference:
   https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450/actions/runs/43629025155
3. Modules PR #2 successfully staged Qualcomm MMRM and Xiaomi QCA6490 WLAN
   module *diagnostic dependency closure* with depmod/modprobe --show-depends:
   https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules/actions/runs/43186709475
4. OEM Cape, Cape-v2 and Capep DTB with mondrian board overlay compiled and
   applied; no independently qualified M11A panel source in that overlay.
   https://github.com/PixelExperience-Reborn/android_kernel_xiaomi_sm8450-devicetrees/actions/runs/43662523661

These successes prove specific build/link relationships, **not** a working
PE-Reborn A17 product. Compile output alone never satisfies the boot gates.

## Read-only on-device evidence collection

Prerequisite: an **already booted, explicitly authorized** developer build on
the physical mondrian using the original Xiaomi-derived kernel. Do not flash
an unqualified build or bypass Android verified boot merely to collect logs.

On a Linux/macOS/Windows computer with Android platform-tools and adb:

    adb devices
    python3 tools/collect_mondrian_a17_runtime.py \
        --out /path/to/private/mondrian-boot-evidence.json

Add --serial <device-selector> only if necessary. The selector, IMEI and
user files are deliberately not collected. The utility calls only a narrow
read-only allowlist of getprop, uname, getenforce, procfs and safe DRM sysfs
paths. It does not request root or modify the phone.

**Interpretation:** a boot identity match is merely evidence that the device
reported codename mondrian, Android release 17, Linux 5.10.81 and boot
completion. It does NOT prove the physical build used the pinned Git commits,
or that the installed ROM is PE-Reborn. Presence of msm_drm, MMRM, WLAN or
Goodix modules in /proc/modules does not prove they are functioning, and
absence from that file does not reject a potentially built-in driver.

The collector writes a local JSON summary; nothing is uploaded to GitHub or
sent to an external endpoint. Review the contents before sharing. Its
qualification section intentionally remains false until independent physical
tests and signed build provenance are available.

## Required real hardware test matrix — all currently NOT QUALIFIED

| Area | Required on-device evidence and expected outcome |
|---|---|
| Boot chain | Verified provenance for boot.img / vendor_boot.img / dtbo.img, A/B slot, AVB and original Xiaomi board-id; repeat cold boot and recovery |
| Kernel ABI | Actual kernel config/version, Module.symvers and exact external module vermagic/depmod match; no unresolved symbols or failed loads |
| Storage | Mount genuine EROFS system/vendor, F2FS encrypted /data, ext4 /metadata; first-stage init, KeyMint FBE and successful unlock; repeat OTA A/B |
| Display | Real Xiaomi M11A revision verified against factory DT, panel power, DSC, 60/90/120 Hz if stock supports, ESD recovery, display wake/doze |
| Input | OEM Goodix controller/firmware, multi-touch, no phantom touches, proximity/pocket behavior, touch suspend/resume |
| UDFPS | Real fingerprint enroll/authentication plus correct OLED local-HBM activation, timeouts, cancel and safe shutdown |
| Power | Qualcomm CPU/GPU thermal throttling, frequency QoS, temperature alarms, long-run charging and thermal soak with device-safe workload |
| WLAN | Xiaomi QCA6490 firmware load, association, WPA2/WPA3 if supported, roaming, suspend/resume and recovery; RF legality/carrier constraints |
| Stability | Repeated sleep/wake and idle, reboot and shutdown, USB, NFC, haptic and battery/charging stability, with regulator lifecycle verified |
| Android 17 | Correct target Android17 release, device VINTF/FCM/KMI compatibility, SELinux enforcing and VTS; be explicit about QPR branch and requirements |
| Other kernel BSP | Mandatory Camera/Video/Audio external kernel dependencies eventually compiled and HW-tested against this **same OEM kernel** |

**Current critical blockers:** the actual Xiaomi stock M11A panel timing/DSC
DTS is missing from the selected public manufacturer subset; the final
bootloader-selected production DTBO has not been built or tested; vendor_dlkm
module install order and firmware are not qualified; no authenticated
physical PE-Reborn A17 boot or full HAL/VINTF/SELinux test has been observed.
The native Android 17 device trees are still scaffolds.

## Next task by strict project order

Maintain Linux 5.10.81 while completing real OEM M11A source recovery and
matching Kernel/Modules/Devicetrees, prepare a signed device test build with
appropriate AOSP17 and OEM firmware interfaces, and run the above hardware
suite on the specific mondrian. No Camera/Video/Audio kernel porting should be
declared complete before this hardware validation gate is closed.

The audit workflow tests the **collector** with simulated adb responses only.
A PASS on that CI is not a real-device PASS.
