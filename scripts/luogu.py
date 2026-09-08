"""Normalize a user-saved Luogu practice page without making network requests.

The practice page proves that a problem was passed, but supplies no AC timestamp.
Its capture time is provenance only and must never become a submission event.
"""
from __future__ import annotations

import datetime as dt
import re

BASE = "https://www.luogu.com.cn"
UID = 571082
HANDLE = "Lucius7"
SOURCE_URL = f"{BASE}/user/{UID}/practice"


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Luogu {field} must be a nonempty string")
    return " ".join(value.split())


def _reported_count(value, label):
    if not isinstance(value, str):
        raise ValueError(f"Luogu reported {label} count is missing or invalid")
    match = re.fullmatch(rf"\s*{label}\s*(0|[1-9][0-9]*)\s*", value)
    if not match:
        raise ValueError(f"Luogu reported {label} count is missing or invalid")
    return int(match[1])


def _capture_time(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value
    ):
        raise ValueError("Luogu capturedAt must be an RFC 3339 timestamp with timezone")
    try:
        date = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.timestamp() <= 0:
            raise ValueError
    except ValueError:
        raise ValueError("Luogu capturedAt is not a valid timestamp") from None
    return value


def _problem(value, difficulty_label=None):
    if not isinstance(value, dict):
        raise ValueError("Luogu problem must be an object")
    pid = value.get("id")
    if not isinstance(pid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,127}", pid):
        raise ValueError("Luogu problem ID is invalid")
    url = f"{BASE}/problem/{pid}"
    if value.get("url") != url:
        raise ValueError("Luogu problem URL does not match its ID and official origin")
    return {
        "id": f"luogu:{pid}",
        "platform": "luogu",
        "contestId": None,
        "index": pid,
        "name": _text(value.get("title"), "problem title"),
        "url": url,
        "difficulty": None,
        "difficultyLabel": difficulty_label,
    }


def normalize_capture(document):
    """Return source data from a saved public practice-page capture.

    ``reportedCounts.submitted`` retains the page's displayed summary, whose
    meaning is not a verified number of individual submissions. Only a future
    submission-history source may supply ``submission_count`` or ``accepted``.
    """
    if not isinstance(document, dict):
        raise ValueError("Luogu capture must be an object")
    if document.get("platform") != "luogu":
        raise ValueError("Luogu capture platform must be luogu")
    if type(document.get("uid")) is not int or document["uid"] != UID:
        raise ValueError("Luogu capture UID does not match the configured user")
    if document.get("handle") != HANDLE:
        raise ValueError("Luogu capture handle does not match the configured user")
    if document.get("sourceUrl") != SOURCE_URL:
        raise ValueError("Luogu sourceUrl must be the configured user's public practice page")
    captured_at = _capture_time(document.get("capturedAt"))
    reported_solved = _reported_count(document.get("reportedSolved"), "通过")
    reported_submitted = (
        _reported_count(document["reportedSubmitted"], "提交")
        if "reportedSubmitted" in document else None
    )
    groups = document.get("solvedGroups")
    attempts = document.get("attempted")
    if not isinstance(groups, list) or not isinstance(attempts, list):
        raise ValueError("Luogu solvedGroups and attempted must be arrays")

    problems = {}
    solved = set()

    def add_problem(value, label=None):
        problem = _problem(value, label)
        key = problem["id"]
        old = problems.get(key)
        if old:
            if old["name"] != problem["name"]:
                raise ValueError("Luogu duplicate problem titles disagree")
            if label is not None and old["difficultyLabel"] not in (None, label):
                raise ValueError("Luogu duplicate problem difficulty groups disagree")
            if label is not None:
                old["difficultyLabel"] = label
        else:
            problems[key] = problem
        return key

    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("problems"), list):
            raise ValueError("Luogu solved group must contain a problems array")
        label = _text(group.get("difficulty"), "difficulty label")
        for value in group["problems"]:
            solved.add(add_problem(value, label))

    if len(solved) != reported_solved:
        raise ValueError("Luogu reported solved count disagrees with unique captured problems")
    attempted = set(solved)
    for value in attempts:
        attempted.add(add_problem(value))

    return {
        "problems": problems,
        "contests": {},
        "accepted": [],
        "attempted": attempted,
        "undatedSolved": sorted(solved),
        "capturedAt": captured_at,
        "reportedCounts": {"solved": reported_solved, "submitted": reported_submitted},
        "profile": {
            "handle": HANDLE,
            "url": f"{BASE}/user/{UID}",
            "rating": None,
            "maxRating": None,
            "rank": None,
            "lastSuccess": None,
        },
        "warnings": ["洛谷通过题目来自公开主页；AC 时间未知，不计入每日记录。"],
        "submission_count": None,
    }
