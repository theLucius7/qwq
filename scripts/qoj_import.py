"""Normalize explicitly exported QOJ browser data without making network requests.

The export contains submission table fields, pagination controls, and contest
tables only. Browser cookies, source code, and arbitrary browser state are neither
needed nor accepted as a data source by this module.
"""
from __future__ import annotations

import datetime as dt
from html import escape
import re
from urllib.parse import parse_qs, urlencode, urlparse

import qoj


def _capture_header(export, label):
    if not isinstance(export, dict) or export.get("platform") != "qoj":
        raise ValueError(f"{label}: expected a QOJ capture")
    handle = export.get("handle")
    if not isinstance(handle, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", handle):
        raise ValueError(f"{label}: invalid account")
    captured_at = export.get("capturedAt")
    if not isinstance(captured_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", captured_at):
        raise ValueError(f"{label}: capturedAt must be a UTC RFC 3339 timestamp")
    try:
        dt.datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{label}: invalid capturedAt timestamp") from None
    if not isinstance(export.get("pages"), list):
        raise ValueError(f"{label}: pages must be an array")
    return handle, captured_at


def _text(record, field, label):
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}: missing {field}")
    return value


def _submission_html(page, handle):
    rows = page.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= qoj.SUBMISSIONS_PAGE_SIZE:
        raise ValueError("QOJ capture page must contain between 1 and 10 verified submission rows")
    parts = ["<table><tbody>"]
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("QOJ capture submission row must be an object")
        identifier = _text(row, "id", "QOJ submission")
        match = re.fullmatch(r"#?([1-9]\d*)", identifier)
        if not match:
            raise ValueError("QOJ capture submission ID is invalid")
        submitter = row.get("submitter")
        submitter_url = row.get("submitterUrl")
        if submitter_url is not None:
            if not isinstance(submitter_url, str) or qoj.local_path(submitter_url).rstrip("/") != f"/user/profile/{handle}":
                raise ValueError("QOJ capture submitter profile identifies another user or origin")
            if submitter not in (handle, f"{handle}#"):
                raise ValueError("QOJ capture submitter label is not recognized")
        elif submitter != handle:
            raise ValueError("QOJ capture includes submissions for another user")
        problem_url = _text(row, "problemUrl", "QOJ submission")
        if qoj.problem_reference(problem_url) is None:
            raise ValueError("QOJ capture problem URL is invalid")
        problem = _text(row, "problem", "QOJ submission")
        verdict = _text(row, "verdict", "QOJ submission")
        submit_time = _text(row, "submitTime", "QOJ submission")
        attributes = []
        for field, attribute in (("score", "data-score"), ("fullScore", "data-full")):
            if field not in row:
                raise ValueError(f"QOJ capture submission is missing {field}")
            value = row[field]
            if value is not None:
                if not isinstance(value, str) or not value:
                    raise ValueError(f"QOJ capture {field} must be a score string or null")
                attributes.append(f'{attribute}="{escape(value, quote=True)}"')
        if (row["score"] is None) != (row["fullScore"] is None):
            raise ValueError("QOJ capture score and fullScore must both be present or both be null")
        parts.append(
            f'<tr><td><a href="/submission/{match[1]}">#{match[1]}</a></td>'
            f'<td><a href="{escape(problem_url, quote=True)}">{escape(problem)}</a></td>'
            f'<td><a href="/user/profile/{escape(handle, quote=True)}">{escape(submitter)}</a></td>'
            f'<td><a {" ".join(attributes)}>{escape(verdict)}</a></td>'
            '<td></td><td></td><td></td><td></td>'
            f'<td>{escape(submit_time)}</td></tr>'
        )
    parts.append("</tbody></table>")
    pager = page.get("pager")
    if not isinstance(pager, list) or not pager:
        raise ValueError("QOJ capture pagination controls are missing")
    parts.append('<ul class="pagination">')
    for offset, item in enumerate(pager):
        if not isinstance(item, dict) or not isinstance(item.get("active"), bool) or not isinstance(item.get("disabled"), bool):
            raise ValueError("QOJ capture pagination state is invalid")
        if item["active"] and item["disabled"]:
            raise ValueError("QOJ capture current page cannot be disabled")
        text = item.get("text")
        if not isinstance(text, str):
            raise ValueError("QOJ capture pagination label is invalid")
        url = item.get("url")
        if url is not None and not isinstance(url, str):
            raise ValueError("QOJ capture pagination URL is invalid")
        if not item["disabled"] and not url:
            raise ValueError("QOJ capture enabled pagination link is missing")
        classes = "page-item" + (" active" if item["active"] else "") + (" disabled" if item["disabled"] else "")
        href = f' href="{escape(url, quote=True)}"' if url else ""
        label = escape(text)
        if not text and not item["active"]:
            if offset == 0:
                label = '<span class="glyphicon glyphicon-backward"></span>'
            elif offset == len(pager) - 1:
                label = '<span class="glyphicon glyphicon-forward"></span>'
            else:
                raise ValueError("QOJ capture pagination direction is not recognized")
        parts.append(f'<li class="{classes}"><a{href}>{label}</a></li>')
    parts.append("</ul>")
    return "".join(parts)


class _CapturedPages:
    """A finite in-memory reader: unknown URLs fail, with no network fallback."""

    def __init__(self, pages):
        self.pages = pages

    def get(self, url):
        if url not in self.pages:
            raise ValueError("QOJ capture is missing a required page; no network request was made")
        return self.pages[url]


def normalize_capture(submissions_export, contests_export, previous=None):
    """Return qoj.collect fields plus the submission capture's capturedAt.

    ``previous`` may supply a complete contest catalogue from a previous QOJ
    source snapshot. Exported catalogues take precedence. Only contests named by
    actual submission URLs are included, even when extra contests were exported.
    The caller owns snapshot validation and persistence.
    """
    handle, captured_at = _capture_header(submissions_export, "QOJ submissions")
    contest_handle, _ = _capture_header(contests_export, "QOJ contests")
    if contest_handle != handle:
        raise ValueError("QOJ capture accounts do not match")
    source_url = submissions_export.get("sourceUrl")
    if not isinstance(source_url, str):
        raise ValueError("QOJ submission sourceUrl is missing")
    source = urlparse(source_url)
    query = parse_qs(source.query, keep_blank_values=True)
    if not qoj.trusted_origin(source) or source.path != "/submissions" or source.fragment or query.get("submitter") != [handle] or query.get("page", ["1"]) != ["1"] or set(query) - {"submitter", "page"}:
        raise ValueError("QOJ submission sourceUrl must identify the captured account's submission history")
    exported_pages = submissions_export["pages"]
    if not exported_pages:
        raise ValueError("QOJ submission capture has no verified pages")
    documents, all_rows = {}, []
    for number, page in enumerate(exported_pages, start=1):
        if not isinstance(page, dict) or type(page.get("page")) is not int or page["page"] != number:
            raise ValueError("QOJ capture pages must be consecutive, beginning at page 1")
        document = _submission_html(page, handle)
        rows, more = qoj.parse_submissions(document, handle, number)
        expected_more = number < len(exported_pages)
        if more != expected_more:
            raise ValueError("QOJ capture has missing pages or its last page is not verified as final")
        if expected_more and len(rows) != qoj.SUBMISSIONS_PAGE_SIZE:
            raise ValueError("QOJ capture has an incomplete intermediate page")
        documents[f"{qoj.BASE}/submissions?{urlencode({'submitter': handle, 'page': number})}"] = document
        all_rows.extend(rows)
    ids = [row["id"] for row in all_rows]
    if any(left <= right for left, right in zip(ids, ids[1:])):
        raise ValueError("QOJ capture submission IDs must be distinct and ordered newest first")
    capture_epoch = dt.datetime.fromisoformat(captured_at.replace("Z", "+00:00")).timestamp()
    if any(row["epoch"] > capture_epoch for row in all_rows):
        raise ValueError("QOJ capture timestamp predates a captured submission")

    required_contests = {row["contestId"] for row in all_rows if row["contestId"] is not None}
    exported_contests = {}
    for page in contests_export["pages"]:
        if not isinstance(page, dict) or type(page.get("cid")) is not int or page["cid"] <= 0:
            raise ValueError("QOJ capture contest ID is invalid")
        cid = page["cid"]
        if cid in exported_contests:
            raise ValueError("QOJ capture repeats a contest page")
        exported_contests[cid] = page
    for cid in required_contests & exported_contests.keys():
        page = exported_contests[cid]
        headings = page.get("headings")
        if not isinstance(headings, list) or not headings or not all(isinstance(heading, str) and heading.strip() for heading in headings):
            raise ValueError("QOJ capture contest headings are missing")
        table = _text(page, "table", "QOJ contest capture")
        document = "".join(f"<h1>{escape(heading)}</h1>" for heading in headings) + table
        qoj.parse_contest(document, cid)
        documents[f"{qoj.BASE}/contest/{cid}"] = document

    cached = None
    if previous is not None:
        if not isinstance(previous, dict) or previous.get("platform") != "qoj" or previous.get("handle") != handle or previous.get("schemaVersion") != 1:
            raise ValueError("QOJ previous snapshot account or schema does not match")
        old_problems, old_contests = previous.get("problems"), previous.get("contests")
        if not isinstance(old_problems, list) or not isinstance(old_contests, list):
            raise ValueError("QOJ previous snapshot catalogue is invalid")
        problem_ids = {problem.get("id") for problem in old_problems if isinstance(problem, dict)}
        kept = []
        for contest in old_contests:
            if not isinstance(contest, dict):
                raise ValueError("QOJ previous snapshot contest is invalid")
            match = re.fullmatch(r"qoj:([1-9]\d*)", str(contest.get("id", "")))
            if not match:
                raise ValueError("QOJ previous snapshot contest ID is invalid")
            cid = int(match[1])
            if cid not in required_contests or cid in exported_contests:
                continue
            keys = contest.get("problems")
            if contest.get("catalogComplete") is True and isinstance(keys, list) and keys and all(isinstance(key, str) and key in problem_ids for key in keys):
                kept.append(contest)
        cached = {"problems": old_problems, "contests": kept}
    result = qoj.collect(_CapturedPages(documents), handle, cached)
    result["capturedAt"] = captured_at
    return result
