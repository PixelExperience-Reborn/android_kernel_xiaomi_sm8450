#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Create a wholly separate PE-Reborn kernel source branch FROM Xiaomi's OEM
# release, not from LF52406 or a LineageOS-derived source snapshot.
set -euo pipefail

[[ $# == 2 ]] || { echo "Usage: $0 <PE kernel target checkout> <Xiaomi OEM checkout>" >&2; exit 2; }
TARGET="$(realpath "$1")"
OEM="$(realpath "$2")"

OEM_COMMIT="989b27aa8391a2ede9b067b53877c4c3343955fe"
OEM_TREE="cc1d5e5fc0f576c3ba3a7a8497de53f6e6023dc8"
PE_BASE="8e022b75c1ce4746951179c193088807597ed2fc"
NEW_BRANCH="bringup/a17-mondrian-xiaomi-oem-base-20261109"

fail() { echo "[FAIL] $*" >&2; exit 1; }

[[ -d "$TARGET/.git" && -d "$OEM/.git" && "$TARGET" != "$OEM" ]] ||
  fail "Expected two separate Git checkouts"
[[ "$(git -C "$OEM" rev-parse HEAD)" == "$OEM_COMMIT" ]] ||
  fail "OEM Git commit does not match reviewed Xiaomi mondrian-s-oss"
[[ "$(git -C "$OEM" rev-parse 'HEAD^{tree}')" == "$OEM_TREE" ]] ||
  fail "OEM Git tree does not match reviewed Xiaomi source"
[[ "$(git -C "$TARGET" branch --show-current)" == "seventeen" ]] ||
  fail "This import MUST branch directly from PE-Reborn's original seventeen"
[[ "$(git -C "$TARGET" rev-parse HEAD)" == "$PE_BASE" ]] ||
  fail "PE main branch moved: stop to re-review base before import"
[[ -z "$(git -C "$TARGET" status --porcelain)" ]] ||
  fail "PE destination checkout has uncommitted changes"
if git -C "$TARGET" ls-remote --exit-code origin "refs/heads/$NEW_BRANCH" >/dev/null; then
  fail "OEM import branch already exists; refuse to overwrite"
fi

for name in Makefile COPYING build.config.msm.mondrian \
  modules.list.msm.mondrian modules.vendor_blocklist.msm.mondrian \
  arch/arm64/configs/vendor/mondrian_GKI.config; do
  [[ -f "$OEM/$name" ]] || fail "Missing OEM source file: $name"
done

[[ "$(sed -n '2p' "$OEM/Makefile")" == "VERSION = 5" ]] || fail "OEM not kernel 5.x"
grep -Fx 'PATCHLEVEL = 10' "$OEM/Makefile" >/dev/null || fail "OEM not 5.10"
grep -Fx 'SUBLEVEL = 81' "$OEM/Makefile" >/dev/null || fail "Unexpected OEM baseline"
grep -Fx 'MSM_ARCH=mondrian' "$OEM/build.config.msm.mondrian" >/dev/null ||
  fail "Not original Xiaomi mondrian build.config"

COUNT="$(git -C "$OEM" ls-files | wc -l)"
[[ "$COUNT" -gt 40000 ]] || fail "Xiaomi worktree incomplete ($COUNT tracked files)"
echo "[INFO] Pinned Xiaomi source: $OEM_COMMIT; tracked paths: $COUNT"

git -C "$TARGET" switch --quiet -c "$NEW_BRANCH"
# Do not transplant third-party ROM sources, device tree, external modules or
# any LF52406 kernel patch in this OEM-first source stage.
rsync -a --exclude='/.git' "$OEM/" "$TARGET/"

mkdir -p "$TARGET/docs"
cat > "$TARGET/docs/PE_REBORN_MONDRIAN_OEM_SOURCE.md" <<'EOF'
# PixelExperience-Reborn — original Xiaomi mondrian kernel source

**OEM authority:** https://github.com/MiCode/Xiaomi_Kernel_OpenSource/tree/mondrian-s-oss  
**Immutable Xiaomi commit:** `989b27aa8391a2ede9b067b53877c4c3343955fe`  
**Git root tree:** `cc1d5e5fc0f576c3ba3a7a8497de53f6e6023dc8`  
**Device:** POCO F5 Pro / Redmi K60 (`mondrian`, Qualcomm SM8475).  
**Project:** PixelExperience-Reborn, independently developed for clean AOSP 17.

The full source snapshot is an attributed **Xiaomi OEM Linux 5.10.81
starting point**, not a finished Android 17 kernel. The Xiaomi release
is incomplete: matching external Qualcomm modules and DT/DTBO, touch
and fingerprint firmware, exact Common Kernel and KMI/toolchain may not
be present. Never invent missing files or declare a full bootable
kernel based only on an OEM source checkout.

The prior LF52406/LineageOS 5.10.269 tree was intentionally **not**
imported into this branch. Individual pieces may be evaluated later as
technical references, compared against Xiaomi's device-specific
implementation, and adapted as new reviewed commits with attribution.
Kernel-source reuse is distinct from inheriting a ROM platform/product.

Retain the original COPYING/LICENSES/SPDX notices; do not copy
proprietary binaries without appropriate rights. Production image,
external-module, DTBO, AOSP17 QPR/ABI, encryption and physical hardware
qualification remain pending. `seventeen` is unchanged.
EOF

# Force inclusion of only existing source worktree objects: Xiaomi itself
# tracks files under ignore rules and symlinks that ordinary git add omits.
git -C "$TARGET" add --all --force
# Compare every OEM Git path, Git mode, and exact Git blob identity in one pass.
python3 - "$OEM" "$TARGET" <<'PY'
import subprocess, sys
from pathlib import Path
src, dst = [Path(s) for s in sys.argv[1:]]
def index(root):
    out = subprocess.check_output(["git", "-C", str(root),
                                   "ls-files", "--stage", "-z"])
    result = {}
    for record in out.split(b"\0"):
        if record:
            attributes, name = record.split(b"\t", 1)
            mode, sha, stage = attributes.split()
            if stage != b"0": raise SystemExit("unmerged index")
            result[name] = (mode, sha)
    return result
original, imported = index(src), index(dst)
mismatches = [name.decode("utf-8", errors="replace")
              for name, expected in original.items()
              if imported.get(name) != expected]
if mismatches:
    raise SystemExit(f"[FAIL] {len(mismatches)} OEM source paths changed/missing: {mismatches[:15]}")
print(f"[PASS] Every OEM Git object matches: {len(original)} files incl. mode and symlinks")
PY

git -C "$TARGET" config user.name 'github-actions[bot]'
git -C "$TARGET" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git -C "$TARGET" commit -q -m "kernel(mondrian): establish full Xiaomi OEM 5.10.81 source baseline" \
  -m "OEM MiCode/Xiaomi_Kernel_OpenSource@989b27aa8391a2ede9b067b53877c4c3343955fe" \
  -m "Independent PE-Reborn AOSP17 kernel bring-up; no third-party ROM imports"
echo "[INFO] OEM source commit: $(git -C "$TARGET" rev-parse HEAD)"
git -C "$TARGET" push --porcelain origin "HEAD:refs/heads/$NEW_BRANCH"
echo "[PASS] Published actual Xiaomi OEM source tree: $NEW_BRANCH"
