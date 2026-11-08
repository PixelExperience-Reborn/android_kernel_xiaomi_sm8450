#!/usr/bin/env python3
"""Ensure every upstream LF kernel tracked path was imported byte-for-byte.

Runs ONLY on the dedicated PE-Reborn full-source branch. A verified source
snapshot can retain additional PE auditing files, but must not silently lose
kernel files, symlinks, executable permissions or original GPL notices.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PINNED_COMMIT = "283772ceb84491fd446e340fd211d45fb9dd9a36"
PINNED_TREE = "a621bf4b1939281af398ef5248e86222a9bfdfa3"
DEST_BRANCH = "bringup/a17-mondrian-kernel-full-source-20261108"


def run_git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True,
        capture_output=True,
    ).stdout


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def index_of(root: Path) -> dict[str, tuple[str, str]]:
    records: dict[str, tuple[str, str]] = {}
    raw = run_git(root, "ls-files", "--stage", "-z")
    for record in raw.split(b"\x00"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        mode, blob, stage = meta.split()
        require(stage == b"0", "unmerged file in Git index")
        key = os.fsdecode(path)
        require(key not in records, f"duplicate tracked path: {key}")
        records[key] = mode.decode(), blob.decode()
    return records


def repair(source: Path, target: Path, modify: bool) -> int:
    source = source.resolve()
    target = target.resolve()
    require(source != target, "source checkout cannot be target checkout")
    require(run_git(source, "rev-parse", "HEAD").decode().strip() == PINNED_COMMIT,
            "wrong upstream source commit")
    require(run_git(source, "rev-parse", "HEAD^{tree}").decode().strip() == PINNED_TREE,
            "wrong upstream source Git tree")
    branch = run_git(target, "branch", "--show-current").decode().strip()
    require(branch == DEST_BRANCH, f"unsafe branch: {branch}")
    if modify:
        require(not run_git(target, "status", "--porcelain"), "target checkout has uncommitted edits")
    upstream = index_of(source)
    ours = index_of(target)
    require(len(upstream) >= 68000, "upstream checkout is incomplete")

    different = [(path, expected) for path, expected in upstream.items()
                 if ours.get(path) != expected]
    print(f"[INFO] Source paths: {len(upstream)}")
    print(f"[INFO] Imported paths present: {sum(p in ours for p in upstream)}")
    print(f"[INFO] Missing or changed Git object/mode: {len(different)}")
    for path, ((mode, sha)) in different[:25]:
        print(f"[FIX NEEDED] {path}: expected {mode} {sha}, got {ours.get(path)}")
    if not modify:
        require(not different, f"source snapshot incomplete: {len(different)} paths")
        print("[PASS] all upstream source paths match original Git modes and hashes")
        return 0

    # A source import should only have a small number of ignored paths to
    # recover. Refuse mass overwrites after the reviewed snapshot stage.
    require(len(different) <= 100,
            f"unexpected large source delta of {len(different)} paths: manual review required")
    for name, (mode, sha) in different:
        src = source / name
        dst = target / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "120000":
            require(src.is_symlink(), f"upstream symlink missing: {name}")
            if dst.is_symlink() or dst.is_file():
                dst.unlink()
            elif dst.exists():
                raise ValueError(f"refusing to replace directory with symlink: {name}")
            dst.symlink_to(os.readlink(src))
        elif mode in ("100644", "100755"):
            require(src.is_file() and not src.is_symlink(),
                    f"upstream regular file mismatch: {name}")
            require(not dst.is_dir(), f"directory conflict at {name}")
            if dst.is_symlink():
                dst.unlink()
            shutil.copy2(src, dst)
        else:
            raise ValueError(f"unsupported upstream Git mode {mode}: {name}")

        # Git ignore rules from the original tree can exclude tracked
        # *symlinks*. Force-add only files proved to belong to upstream.
        run_git(target, "add", "-f", "--", name)
    remaining = [(p, wanted) for p, wanted in upstream.items()
                 if index_of(target).get(p) != wanted] if different else []
    require(not remaining, f"repair failed to restore {len(remaining)} original Git objects")
    print(f"[PASS] recovered {len(different)} missing/modified upstream paths")
    return len(different)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    count = repair(args.upstream, args.target, args.repair)
    if args.repair:
        # This script only stages files, leaving Git history/push to the
        # tightly scoped caller's reviewed workflow.
        print(f"[PASS] {count} source repairs staged; no branch has been pushed by this tool")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
