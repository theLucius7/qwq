#!/usr/bin/env python3
"""Import explicitly saved public browser records; never perform network requests."""
from __future__ import annotations

import argparse
from pathlib import Path

import luogu
import qoj_import
import sync


def import_records(*, qoj_submissions=None, qoj_contests=None, luogu_practice=None,
                   source_dir=sync.SOURCE_DIR):
    if bool(qoj_submissions) != bool(qoj_contests):
        raise ValueError("QOJ import requires both submissions and contest captures")
    if not qoj_submissions and not luogu_practice:
        raise ValueError("Provide at least one browser capture")
    pending = {}
    if qoj_submissions:
        previous = sync.read_json(source_dir / "qoj.json")
        payload = qoj_import.normalize_capture(
            sync.read_json(Path(qoj_submissions)), sync.read_json(Path(qoj_contests)), previous)
        pending["qoj"] = sync.make_snapshot(
            "qoj", **payload, handle=sync.QOJ_HANDLE, collectionMethod="browser_import")
    if luogu_practice:
        payload = luogu.normalize_capture(sync.read_json(Path(luogu_practice)))
        pending["luogu"] = sync.make_snapshot("luogu", **payload, collectionMethod="browser_import")
    # Validate every capture before replacing any existing source.
    for platform, snapshot in pending.items():
        previous = sync.read_json(source_dir / f"{platform}.json")
        if previous:
            sync.validate(previous)
            old_solved = {event["problemId"] for event in previous["accepted"]} | set(previous.get("undatedSolved", []))
            new_solved = {event["problemId"] for event in snapshot["accepted"]} | set(snapshot.get("undatedSolved", []))
            if old_solved and not new_solved:
                raise ValueError(f"{platform}: empty import would erase an established solved history")
    for platform, snapshot in pending.items():
        sync.atomic_json(source_dir / f"{platform}.json", snapshot)
    return pending


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qoj-submissions", type=Path)
    parser.add_argument("--qoj-contests", type=Path)
    parser.add_argument("--luogu-practice", type=Path)
    args = parser.parse_args()
    snapshots = import_records(**vars(args))
    for platform, snapshot in snapshots.items():
        solved = {event["problemId"] for event in snapshot["accepted"]} | set(snapshot["undatedSolved"])
        print(f"{platform}: imported {len(solved)} solved problems, {len(snapshot['accepted'])} AC events, {len(snapshot['contests'])} contests")
    print("Run python3 scripts/sync.py --offline to rebuild the dashboard.")


if __name__ == "__main__":
    main()
