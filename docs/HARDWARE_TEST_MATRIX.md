# mondrian pre-boot and touch/UDFPS validation matrix

| Gate | Evidence to collect | Pass criteria | Current state |
| --- | --- | --- | --- |
| OEM kernel completeness | OEM `build.config.msm.mondrian` and full dependency manifest | Every referenced source, tool and external module exists | BLOCKED |
| Kernel security | Baseline/ACK commit history, CVE patch list, ABI delta | Security updates without unexplained KMI breakage | BLOCKED |
| Qualcomm modules | Exact .ko list, `modinfo`, `Module.symvers`, CRCs | KMI/symbols and init order match selected kernel | BLOCKED |
| Panel/DTBO | Panel ID, DTS includes, bootloader dtbo selection | Valid dtc and exact on-device panel match | BLOCKED |
| Touch | Input IC/firmware, kernel logs, raw input traces | No invalid/spurious touch frames across 60/120 Hz, charge and resume | BLOCKED |
| UDFPS | Fingerprint vendor HAL, firmware/TEE, screen-off and lockscreen traces | Enroll/auth/cancel/retry work with correct panel brightness | BLOCKED |
| Power/thermal | Runtime PM, IRQ wake, thermal, FOD and frame pacing logs | No thermal/power regressions or touch wake storms | BLOCKED |
| AOSP17 initial | Target-files, GKI/FCM and first device boot | Complete boot and platform compatibility | BLOCKED |
| Android17 QPR1+ | Official support matrix and migration plan | Explicit compatible supported kernel family and tested module set | BLOCKED |
| Security | AVB keys, rollback, FBE/KeyMint, SELinux | Never ship public test keys, disabled verification or permissive rules | BLOCKED |

Gather read-only evidence from an owned/test device. Kernel/input logs may
contain sensitive data; review/redact before publishing any logs.
