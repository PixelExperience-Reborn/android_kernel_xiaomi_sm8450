#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# HOST-ONLY mondrian source candidate Kconfig smoke test.
# DOES NOT compile kernel, modules, DTBO or ROM. NEVER flashes a device.
set -euo pipefail

usage() {
  echo "Usage: $0 <LF kernel source directory> <new scratch output directory>" >&2
  exit 2
}
[[ $# == 2 ]] || usage
KERNEL="$(realpath "$1")"
OUT="$(realpath -m "$2")"
EXPECTED="283772ceb84491fd446e340fd211d45fb9dd9a36"

[[ -f "$KERNEL/Makefile" && -f "$KERNEL/scripts/kconfig/merge_config.sh" ]] || {
  echo "[FAIL] not a complete LF kernel source checkout" >&2; exit 1; }
[[ "$(git -C "$KERNEL" rev-parse HEAD)" == "$EXPECTED" ]] || {
  echo "[FAIL] mismatched LF candidate commit" >&2; exit 1; }
[[ "$OUT" != "$KERNEL" && "$OUT" != "$KERNEL/"* && "$OUT" != "$KERNEL/.." ]] || {
  echo "[FAIL] output must not be inside kernel source" >&2; exit 1; }
[[ ! -e "$OUT" ]] || { echo "[FAIL] output path exists, refusing overwrite: $OUT" >&2; exit 1; }
mkdir -p "$OUT"

BASE="$KERNEL/arch/arm64/configs"
for input in gki_defconfig vendor/waipio_GKI.config vendor/xiaomi_GKI.config \
             vendor/mondrian_GKI.config vendor/debugfs.config; do
  [[ -f "$BASE/$input" ]] || { echo "[FAIL] missing $input" >&2; exit 1; }
done

echo "[INFO] $(git -C "$KERNEL" rev-parse --short=12 HEAD), host: $(uname -srm)"
make -C "$KERNEL" O="$OUT" ARCH=arm64 gki_defconfig

"$KERNEL/scripts/kconfig/merge_config.sh" -m -r -O "$OUT" \
  "$OUT/.config" \
  "$BASE/vendor/waipio_GKI.config" \
  "$BASE/vendor/xiaomi_GKI.config" \
  "$BASE/vendor/mondrian_GKI.config" \
  "$BASE/vendor/debugfs.config"

make -C "$KERNEL" O="$OUT" ARCH=arm64 olddefconfig

python3 - "$OUT/.config" <<'PY'
import pathlib
import sys
f = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
checks = {
    "CONFIG_ARCH_CAPE=y": "CAPE / SM8475 DTS platform",
    "CONFIG_BUILD_ARM64_DT_OVERLAY=y": "DTBO support",
    "CONFIG_TOUCHSCREEN_GOODIX_BRL=m": "Goodix Berlin touch module",
    "CONFIG_FINGERPRINT_GOODIX_TEE=m": "Goodix TEE fingerprint",
    "CONFIG_EROFS_FS=y": "EROFS root filesystem",
    "CONFIG_F2FS_FS=y": "F2FS userdata",
}
missing = [f"{human} ({raw})" for raw, human in checks.items()
           if raw not in f.splitlines()]
if missing:
    print("[FAIL] Kconfig rejected required mondrian settings:")
    print("\n".join("  - " + name for name in missing))
    raise SystemExit(1)
print("[PASS] Kconfig fragments merged and accepted by olddefconfig")
print("[NOTE] No kernel Image, Qualcomm modules, KMI, DTBO, boot.img or Android17 ROM compiled")
PY
