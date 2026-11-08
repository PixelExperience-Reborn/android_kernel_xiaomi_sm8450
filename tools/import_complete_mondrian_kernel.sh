#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# PixelExperience-Reborn: preserve the ACTUAL LF mondrian 5.10 kernel source
# as a pinned, provenance-tracked Git snapshot in a new PE-Reborn branch.
# This script NEVER overwrites seventeen or the audit branch.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <destination-repo-checkout> <cloned-upstream-worktree>" >&2
  exit 2
fi
DEST="$(realpath "$1")"
SOURCE="$(realpath "$2")"

UPSTREAM_REPO="LF52406/android_kernel_xiaomi_sm8450"
UPSTREAM_COMMIT="283772ceb84491fd446e340fd211d45fb9dd9a36"
UPSTREAM_TREE="a621bf4b1939281af398ef5248e86222a9bfdfa3"
XIAOMI_REPO="MiCode/Xiaomi_Kernel_OpenSource"
XIAOMI_BRANCH="mondrian-s-oss"
XIAOMI_COMMIT="989b27aa8391a2ede9b067b53877c4c3343955fe"
NEW_BRANCH="bringup/a17-mondrian-kernel-full-source-20261108"

if [[ ! -d "$DEST/.git" || ! -d "$SOURCE/.git" || "$DEST" == "$SOURCE" ]]; then
  echo "[FAIL] Expected separate Git source and target repositories." >&2
  exit 1
fi
if [[ "$(git -C "$SOURCE" rev-parse HEAD)" != "$UPSTREAM_COMMIT" ||
      "$(git -C "$SOURCE" rev-parse 'HEAD^{tree}')" != "$UPSTREAM_TREE" ]]; then
  echo "[FAIL] LF source does not match immutable public commit/tree." >&2
  exit 1
fi
if [[ "$(git -C "$DEST" branch --show-current)" !=
      "audit/a17-mondrian-kernel-bsp-provenance-20261108" ]]; then
  echo "[FAIL] Import must start from reviewed PE kernel audit branch." >&2
  exit 1
fi
if [[ -n "$(git -C "$DEST" status --porcelain)" ]]; then
  echo "[FAIL] Target checkout is not clean." >&2
  exit 1
fi

if git -C "$DEST" ls-remote --exit-code origin "refs/heads/$NEW_BRANCH" >/dev/null; then
  echo "[FAIL] Source branch already exists; refusing to replace or force-push." >&2
  exit 1
fi

REQUIRED=(
  "Makefile"
  "COPYING"
  "build.config.msm.waipio"
  "modules.list.msm.waipio"
  "arch/arm64/configs/gki_defconfig"
  "arch/arm64/configs/vendor/waipio_GKI.config"
  "arch/arm64/configs/vendor/xiaomi_GKI.config"
  "arch/arm64/configs/vendor/mondrian_GKI.config"
  "arch/arm64/configs/vendor/debugfs.config"
  "io_uring/io_uring.c"
  "drivers/input/touchscreen/goodix_berlin_driver/goodix_brl_spi.c"
  "android/abi_gki_aarch64_qcom"
)
for rel in "${REQUIRED[@]}"; do
  if [[ ! -f "$SOURCE/$rel" ]]; then
    echo "[FAIL] Required source file is missing: $rel" >&2
    exit 1
  fi
done
if [[ ! -L "$SOURCE/arch/arm64/boot/dts/vendor" ||
      "$(readlink "$SOURCE/arch/arm64/boot/dts/vendor")" != "../../../../../sm8450-devicetrees" ]]; then
  echo "[FAIL] External Qualcomm DT symlink does not match reviewed source." >&2
  exit 1
fi

UPSTREAM_FILES="$(git -C "$SOURCE" ls-files | wc -l)"
if [[ "$UPSTREAM_FILES" -lt 30000 ]]; then
  echo "[FAIL] Source snapshot is incomplete ($UPSTREAM_FILES tracked files)." >&2
  exit 1
fi

git -C "$DEST" switch --quiet -c "$NEW_BRANCH"
# This is a full source snapshot, not a subset of audit JSON metadata.
# Keep PE-Reborn audit records/CI while copying all kernel source files.
# Git and actual Linux DTS symlinks are preserved as symlinks.
rsync -a --exclude='/.git' "$SOURCE/" "$DEST/"

mkdir -p "$DEST/.pe-reborn"
cat > "$DEST/.pe-reborn/SOURCE_PROVENANCE.md" <<EOF
# PixelExperience-Reborn — mondrian Linux kernel source origin

This branch contains an actual **Linux 5.10.269 source snapshot** for
POCO F5 Pro / Redmi K60 (`mondrian`, physical Qualcomm SM8475).

- Source repository: https://github.com/$UPSTREAM_REPO
- Source branch: `lineage-24.0`
- Verified source commit: `$UPSTREAM_COMMIT`
- Verified source Git root tree: `$UPSTREAM_TREE`
- OEM reference: https://github.com/$XIAOMI_REPO/tree/$XIAOMI_BRANCH
- Xiaomi's incomplete published source commit: `$XIAOMI_COMMIT`
- Original kernel source remains subject to its own GPL licenses and notices.

This import is a **single-source snapshot** added on top of PE-Reborn
audit commits; it does not claim to retain the full upstream Git history.
The immutable source commit above remains available in the original Git
repository for attribution and future delta/audit comparison.

**Not yet qualified:** Android 17 QPR support, correct Android Common
Kernel/toolchain, externally compiled Qualcomm modules, DTS overlays,
KMI/Module.symvers, Xiaomi firmware, AVB, KeyMint/FBE, vendor_boot or
device boot. Do not flash experimental images. This is not a fork of
LineageOS's ROM/platform product tree; only kernel-source content is
used as an implementation baseline.
EOF

# Verify the imported bytes match original Git blobs. This is stricter
# than merely seeing source-looking filenames in GitHub.
for rel in "${REQUIRED[@]}"; do
  expected="$(git -C "$SOURCE" rev-parse "HEAD:$rel")"
  actual="$(git -C "$DEST" hash-object "$DEST/$rel")"
  if [[ "$expected" != "$actual" ]]; then
    echo "[FAIL] Source snapshot does not match original Git blob: $rel" >&2
    exit 1
  fi
done

git -C "$DEST" add -A
STAGED="$(git -C "$DEST" diff --cached --name-only | wc -l)"
if [[ "$STAGED" -lt 30000 ]]; then
  echo "[FAIL] Source import staged too few files: $STAGED" >&2
  exit 1
fi

git -C "$DEST" config user.name "github-actions[bot]"
git -C "$DEST" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$DEST" commit --quiet \
  -m "kernel(mondrian): import full pinned Linux 5.10.269 source snapshot from LF52406" \
  -m "Source: $UPSTREAM_REPO@$UPSTREAM_COMMIT" \
  -m "OEM evidence: $XIAOMI_REPO@$XIAOMI_COMMIT"

echo "[INFO] Source tracked files: $UPSTREAM_FILES"
echo "[INFO] New source files staged: $STAGED"
echo "[INFO] Source branch commit: $(git -C "$DEST" rev-parse HEAD)"
echo "[INFO] Source HEAD path: $(git -C "$DEST" rev-parse HEAD:Makefile)"
git -C "$DEST" push --porcelain origin "HEAD:refs/heads/$NEW_BRANCH"
echo "[PASS] Full mondrian source snapshot pushed to $NEW_BRANCH"
