#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Reproducible Google Android Clang toolchain for mondrian Xiaomi OEM kernel build qualification.
# Source: official AOSP, not Ubuntu's system clang.
# Pinned kernel-only toolchain, not a Soong or device-wide compiler override.
set -euo pipefail
if [[ $# != 1 ]]; then
  echo "Usage: $0 <non-existing destination directory>" >&2
  exit 2
fi
REPO_URL="https://android.googlesource.com/platform/prebuilts/clang/host/linux-x86"
REPO_COMMIT="c9ed23e2ba198658b630d4b10e09fa980cd43119"
CLANG_REVISION="clang-r614150"
EXPECTED_MAJOR="23"
DEST="$(realpath -m "$1")"
if [[ -e "$DEST" ]]; then
  echo "[FAIL] Destination already exists; refusing to mix compiler versions: $DEST" >&2
  exit 1
fi
mkdir -p "$DEST"
cd "$DEST"
git init -q
git remote add origin "$REPO_URL"
git sparse-checkout init --cone
git sparse-checkout set "$CLANG_REVISION"
git -c protocol.version=2 fetch --quiet --depth=1 --filter=blob:none origin "$REPO_COMMIT"
git checkout -q --detach FETCH_HEAD
ACTUAL="$(git rev-parse HEAD)"
if [[ "$ACTUAL" != "$REPO_COMMIT" ]]; then
  echo "[FAIL] Unpinned compiler repository HEAD: $ACTUAL" >&2
  exit 1
fi
TOOLCHAIN="$DEST/$CLANG_REVISION"
for tool in clang clang++ ld.lld llvm-ar llvm-nm llvm-objcopy llvm-strip; do
  if [[ ! -x "$TOOLCHAIN/bin/$tool" ]]; then
    echo "[FAIL] Missing Android toolchain binary $tool" >&2
    exit 1
  fi
done
VERSION="$("$TOOLCHAIN/bin/clang" --version | head -n1)"
if [[ ! "$VERSION" =~ clang[[:space:]]version[[:space:]]23\. ]]; then
  echo "[FAIL] Expected modern Android Clang 23: $VERSION" >&2
  exit 1
fi
"$TOOLCHAIN/bin/ld.lld" --version | head -n1
echo "[PASS] $VERSION"
echo "[PASS] pinned Android compiler source: $REPO_COMMIT"
echo "[INFO] Use this bin directory as PATH prefix and LLVM=1 LLVM_IAS=1"
