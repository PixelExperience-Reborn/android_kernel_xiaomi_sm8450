#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Preserve Xiaomi's original generic DRM driver and stage official Qualcomm
# SDE/DSI under techpack/display for source/ABI qualification ONLY.
set -euo pipefail

[[ $# == 2 ]] || { echo "Usage: $0 <kernel checkout> <official Qualcomm checkout>" >&2; exit 2; }
KERNEL="$(realpath "$1")"
QCOM="$(realpath "$2")"
SOURCE_REPO="qualcomm-linux/display-driver"
SOURCE_COMMIT="7b546db38822a40bc1beb5a9ace006b6541b947f"
TRIAL_BRANCH="bringup/a17-mondrian-qualcomm-display-trial-20261109"

fail() { echo "[FAIL] $*" >&2; exit 1; }

[[ -d "$KERNEL/.git" && -d "$QCOM/.git" ]] || fail "Need separate Git worktrees"
[[ "$(git -C "$KERNEL" branch --show-current)" == "$TRIAL_BRANCH" ]] ||
  fail "Refuse modification of OEM/main source branch"
[[ -z "$(git -C "$KERNEL" status --porcelain)" ]] ||
  fail "Kernel worktree must be clean before import"
[[ "$(git -C "$QCOM" rev-parse HEAD)" == "$SOURCE_COMMIT" ]] ||
  fail "Qualcomm source changed from audited pinned commit"
[[ -d "$KERNEL/drivers/gpu/drm/msm" ]] ||
  fail "Original Xiaomi generic DRM must be preserved"
[[ ! -e "$KERNEL/techpack/display" ]] ||
  fail "techpack/display already exists: refuse overwrite"
for path in "Kbuild" "Makefile" "LICENSE.txt" "NOTICE" \
            "config/gki_waipiodisp.conf" "config/gki_waipiodispconf.h" \
            "msm/Kbuild" "msm/sde/sde_hw_catalog.c" "msm/dsi/dsi_panel.c"; do
  [[ -f "$QCOM/$path" ]] || fail "Missing official Qualcomm source: $path"
done
grep -Fq 'ifeq ($(CONFIG_ARCH_WAIPIO), y)' "$QCOM/msm/Kbuild" ||
  fail "Official Qualcomm display driver lacks WAIPIO integration"
grep -Fq 'CONFIG_DISPLAY_BUILD=m' "$QCOM/config/gki_waipiodisp.conf" ||
  fail "Invalid Qualcomm WAIPIO display module recipe"

mkdir -p "$KERNEL/techpack/display"
rsync -a --exclude='/.git' "$QCOM/" "$KERNEL/techpack/display/"
cat > "$KERNEL/techpack/display/PE_REBORN_SOURCE_PROVENANCE.md" <<'EOF'
# Official Qualcomm SDE/DSI source candidate for mondrian

Source: https://github.com/qualcomm-linux/display-driver
Pinned commit: \`7b546db38822a40bc1beb5a9ace006b6541b947f\`
Destination: \`techpack/display\` in the **isolated trial branch**.

- The original Xiaomi \`drivers/gpu/drm/msm\` DRM implementation is not
  deleted, modified or enabled by this source import.
- Qualcomm provides \`config/gki_waipiodisp.conf\` and \`msm/Kbuild\`.
- The display controller on SM8475/CAPE and the Xiaomi M11A panel
  still require exact matching DT, kernel ABI, firmware and HWC checks.
- This source snapshot is **not yet known to compile with Xiaomi 5.10.81**,
  to produce a valid \`msm_drm.ko\`, or to support AOSP 17 graphics HAL.
- Do not build both DRM providers into the same kernel or package both
  modules; select one verified target implementation.
- Original upstream LICENSE.txt, NOTICE and file-specific licenses
  have been retained. No vendor blobs are included.
- The Qualcomm code itself references other multimedia drivers/headers
  and version-dependent kernel APIs; validate these before integration.

This source trial cannot be merged into the production \`seventeen\`
branch until exact compile, API/ABI, display panel and boot tests pass.
EOF
git -C "$KERNEL" add -f -- techpack/display

python3 - "$QCOM" "$KERNEL" <<'PY'
import os, subprocess, sys
from pathlib import Path
src, dst = map(Path, sys.argv[1:])
def inventory(repo, prefix=b""):
    raw = subprocess.check_output(["git", "-C", str(repo), "ls-files", "-s", "-z"])
    entries = {}
    for rec in raw.split(b"\0"):
        if not rec: continue
        props, path = rec.split(b"\t", 1)
        mode, sha, stage = props.split()
        if stage != b"0": raise SystemExit("unmerged Git index")
        if path.startswith(prefix):
            entries[path[len(prefix):]] = (mode, sha)
    return entries
original = inventory(src)
target = inventory(dst, b"techpack/display/")
missing = [os.fsdecode(p) for p, obj in original.items() if target.get(p) != obj]
if len(original) < 450 or missing:
    raise SystemExit("[FAIL] Qualcomm source object mismatch: " + str(missing[:15]))
print(f"[PASS] Exact official Qualcomm source Git blobs and modes: {len(original)}")
PY
git -C "$KERNEL" config user.name "github-actions[bot]"
git -C "$KERNEL" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git -C "$KERNEL" commit -q \
  -m "display(mondrian): stage pinned official Qualcomm WAIPIO SDE/DSI source" \
  -m "Source: $SOURCE_REPO@$SOURCE_COMMIT" \
  -m "Preserve original Xiaomi generic DRM; no module selected"
git -C "$KERNEL" push --porcelain origin "HEAD:refs/heads/$TRIAL_BRANCH"
echo "[PASS] Official Qualcomm source trial published; main OEM kernel preserved"
