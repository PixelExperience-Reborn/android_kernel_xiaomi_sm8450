#!/usr/bin/env python3
"""Fail-closed, read-only checker for pinned external mondrian BSP evidence.

Default is OFFLINE schema checking only. --online additionally fetches immutable
GitHub commit objects and raw public files, checks their Git blob SHA-1 and
asserts concrete published facts. Neither mode proves build/boot compatibility.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def git_blob_sha(raw):
    header = b"blob " + str(len(raw)).encode("ascii") + b"\\0"
    return hashlib.sha1(header + raw).hexdigest()


def validate_content(raw, entry):
    errors = []
    expected = entry["blob_sha"]
    actual = git_blob_sha(raw)
    if actual != expected:
        errors.append(f"Git blob SHA mismatch: expected {expected}, got {actual}")
    data = raw.decode("utf-8")
    for needle in entry.get("must_contain", []):
        if needle not in data:
            errors.append(f"Required string absent: {needle!r}")
    for needle in entry.get("must_not_contain", []):
        if needle in data:
            errors.append(f"Forbidden string present: {needle!r}")
    if "module_list" in entry:
        lines = [line.strip() for line in data.splitlines() if line.strip()]
        counts = Counter(lines)
        duplicates = sorted(name for name, n in counts.items() if n > 1)
        expected_list = entry["module_list"]
        if len(lines) != expected_list["entries"]:
            errors.append("OEM module entry count changed")
        if len(counts) != expected_list["unique"]:
            errors.append("OEM unique module count changed")
        if duplicates != sorted(expected_list["duplicates"]):
            errors.append("OEM duplicate module inventory changed")
    return errors


def load_manifest(root=ROOT):
    inventory = json.loads((root / "source-candidates.json").read_text(encoding="utf-8"))
    evidence = json.loads((root / "reference-evidence.json").read_text(encoding="utf-8"))
    if inventory["schema_version"] != 2 or evidence["schema_version"] != 1:
        raise ValueError("Unexpected inventory/evidence schema version")
    sources = {source["role"]: source for source in inventory["references"]}
    if len(sources) != len(inventory["references"]):
        raise ValueError("Duplicate source roles")
    if len(evidence["files"]) != len({(f["role"], f["path"]) for f in evidence["files"]}):
        raise ValueError("Duplicate evidence records")
    for source in sources.values():
        if not REPO.fullmatch(source["repository"]):
            raise ValueError("Unexpected repository path")
        for key in ("source_commit_sha", "source_tree_sha"):
            if not SHA.fullmatch(source[key]):
                raise ValueError(f"Invalid {key} for {source['repository']}")
        if source["source_commit_sha"] == source["source_tree_sha"]:
            raise ValueError("Commit SHA mistaken for Git tree SHA")
    for f in evidence["files"]:
        if f["role"] not in sources:
            raise ValueError(f"Unknown source role: {f['role']}")
        if not SHA.fullmatch(f["blob_sha"]):
            raise ValueError(f"Invalid Git blob SHA: {f['path']}")
        path = f["path"]
        if path.startswith("/") or ".." in Path(path).parts or "\\\\" in path:
            raise ValueError(f"Unsafe path: {path}")
        if not f.get("must_contain"):
            raise ValueError(f"Missing content assertions: {path}")
    if inventory["target"]["device"] != "mondrian":
        raise ValueError("Only mondrian is in scope")
    if any(inventory["gates"].values()):
        raise ValueError("Published sources must not be marked as qualified")
    return inventory, evidence, sources


def get_url(url, token=None):
    headers = {"User-Agent": "PE-Reborn-mondrian-source-audit", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        return response.read()


def online_verify(sources, evidence):
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    for source in sources.values():
        repo = source["repository"]
        commit = source["source_commit_sha"]
        url = f"https://api.github.com/repos/{repo}/git/commits/{commit}"
        metadata = json.loads(get_url(url, token))
        if metadata.get("sha") != commit:
            raise ValueError(f"GitHub commit mismatch: {repo}")
        if metadata.get("tree", {}).get("sha") != source["source_tree_sha"]:
            raise ValueError(f"GitHub tree mismatch: {repo}")
        print(f"[PASS] commit/tree: {repo}@{commit[:12]}")
    for file in evidence["files"]:
        source = sources[file["role"]]
        repo = source["repository"]
        commit = source["source_commit_sha"]
        path = quote(file["path"], safe="/")
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{path}"
        errors = validate_content(get_url(url), file)
        if errors:
            raise ValueError(f"{repo}:{path}: " + "; ".join(errors))
        print(f"[PASS] Git blob/content: {repo}:{path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="Verify published remote blobs and commit/tree ids")
    args = parser.parse_args()
    _, evidence, sources = load_manifest()
    print(f"[PASS] local manifest schema: {len(sources)} repositories, {len(evidence['files'])} file records")
    if args.online:
        online_verify(sources, evidence)
        print("[PASS] public evidence is pinned and consistent (NOT a kernel build/boot test)")
    else:
        print("[INFO] OFFLINE only: upstream GitHub contents were NOT checked. Use --online for evidence checks.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, UnicodeError, HTTPError, URLError, OSError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        sys.exit(1)
