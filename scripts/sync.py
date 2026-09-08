#!/usr/bin/env python3
"""Fetch public histories, replace successful snapshots atomically, build Pages data."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
HANDLE = "Lucius7"
AT = "https://kenkoooo.com/atcoder"
CF = "https://codeforces.com"
SOURCE_DIR = ROOT / "data" / "sources"
OUTPUT = ROOT / "public" / "data" / "dashboard.json"


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Client:
    def __init__(self):
        self.last_request = {}

    def get(self, url, as_json=True):
        host = urlparse(url).hostname
        interval = 2.2 if host == "codeforces.com" else 1.1
        for attempt in range(3):
            delay = interval - (time.monotonic() - self.last_request.get(host, 0))
            if delay > 0:
                time.sleep(delay)
            self.last_request[host] = time.monotonic()
            request = Request(url, headers={"User-Agent": "Lucius7-AC-Journal/1.0 (+https://github.com/theLucius7/qwq)", "Accept": "application/json" if as_json else "text/html"})
            try:
                with urlopen(request, timeout=45) as response:
                    value = response.read().decode("utf-8")
                if not as_json:
                    return value
                value = json.loads(value)
                if host == "codeforces.com" and "/api/" in url:
                    if value.get("status") != "OK":
                        raise ValueError(value.get("comment", "Codeforces API failed"))
                    return value["result"]
                return value
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
                if attempt == 2:
                    raise RuntimeError(f"{url}: {error}") from error
                time.sleep(3 * (attempt + 1))
        raise AssertionError("Unreachable")


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def atcoder_submissions(client):
    cursor, records = 0, {}
    while True:
        page = client.get(f"{AT}/atcoder-api/v3/user/submissions?{urlencode({'user': HANDLE, 'from_second': cursor})}")
        if not isinstance(page, list):
            raise ValueError("AtCoder returned an invalid submission page")
        for record in page:
            records[record["id"]] = record
        if len(page) < 500:
            break
        next_cursor = max(record["epoch_second"] for record in page)
        if next_cursor <= cursor:
            raise ValueError("AtCoder timestamp pagination did not advance; refusing a truncated history")
        cursor = next_cursor  # Inclusive overlap avoids dropping same-second submissions.
    return list(records.values())


def codeforces_submissions(client):
    offset, records = 1, {}
    while True:
        page = client.get(f"{CF}/api/user.status?{urlencode({'handle': HANDLE, 'from': offset, 'count': 1000})}")
        if not isinstance(page, list):
            raise ValueError("Codeforces returned an invalid submission page")
        before = len(records)
        for record in page:
            records[record["id"]] = record
        if len(page) < 1000:
            break
        if len(records) == before:
            raise ValueError("Codeforces pagination did not advance")
        # Overlap a small window in case new submissions shift the next offset.
        offset += 990
    return list(records.values())


def atcoder_kind(contest_id):
    if contest_id.startswith("adt_"):
        return "ADT"
    for kind in ("abc", "arc", "agc", "ahc"):
        if re.match(rf"^{kind}\d+$", contest_id):
            return kind.upper()
    return "其他 AtCoder"


def codeforces_kind(contest):
    if int(contest["id"]) >= 100000:
        return "Gym"
    title = contest["name"]
    if "Educational" in title:
        return "Educational"
    divisions = re.findall(r"Div\.?\s*([1-4])", title)
    if len(divisions) > 1:
        return "Div. " + " + ".join(divisions)
    if divisions:
        return f"Div. {divisions[0]}"
    return "其他 Codeforces"


def cf_problem(raw):
    contest_id = raw.get("contestId")
    index = raw["index"]
    if contest_id is None:
        # API also defines special problemsets without a contest ID.
        problemset = raw.get("problemsetName", "unknown")
        key = f"codeforces:problemset:{problemset}:{index}"
        url = f"{CF}/problemsets/{problemset}/problem/99999/{index}"
    else:
        key = f"codeforces:{contest_id}:{index}"
        path = "gym" if int(contest_id) >= 100000 else "contest"
        url = f"{CF}/{path}/{contest_id}/problem/{index}"
    return {"id": key, "platform": "codeforces", "contestId": f"codeforces:{contest_id}" if contest_id is not None else None, "index": index, "name": raw["name"], "url": url, "difficulty": raw.get("rating")}


def index_order(value):
    return [(0, int(part)) if part.isdigit() else (1, part) for part in re.split(r"(\d+)", value)]


class GymProblems(HTMLParser):
    """Read only official problem-table links, never unrelated page links."""
    def __init__(self, contest_id):
        super().__init__()
        self.contest_id = str(contest_id)
        self.table_depth = 0
        self.active_index = None
        self.text = []
        self.problems = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if self.table_depth:
                self.table_depth += 1
            elif "problems" in attrs.get("class", "").split():
                self.table_depth = 1
        if self.table_depth and tag == "a":
            match = re.fullmatch(rf"/gym/{self.contest_id}/problem/([A-Za-z0-9]+)", attrs.get("href", ""))
            if match:
                self.active_index, self.text = match.group(1), []

    def handle_data(self, data):
        if self.active_index:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.active_index:
            title = " ".join("".join(self.text).split())
            if title:
                previous = self.problems.get(self.active_index)
                if not previous or title != self.active_index:
                    self.problems[self.active_index] = title
            self.active_index = None
        if tag == "table" and self.table_depth:
            self.table_depth -= 1


def parse_gym(document, contest_id):
    parser = GymProblems(contest_id)
    parser.feed(document)
    return [cf_problem({"contestId": int(contest_id), "index": index, "name": name}) for index, name in sorted(parser.problems.items(), key=lambda pair: index_order(pair[0]))]


def optional(client, url, fallback, warnings, message, as_json=True):
    try:
        return client.get(url, as_json)
    except RuntimeError as error:
        print(f"Warning: {error}", flush=True)
        warnings.append(message)
        return fallback


def collect_atcoder(client, previous):
    warnings = []
    submissions = atcoder_submissions(client)
    print(f"AtCoder: {len(submissions)} submissions", flush=True)
    raw_problems = client.get(f"{AT}/resources/problems.json")
    raw_contests = client.get(f"{AT}/resources/contests.json")
    associations = client.get(f"{AT}/resources/contest-problem.json")
    models = optional(client, f"{AT}/resources/problem-models.json", {}, warnings, "估计难度暂不可用")
    problems = {}
    for item in raw_problems:
        difficulty = models.get(item["id"], {}).get("difficulty")
        if difficulty is not None:
            difficulty = math.floor(400 * math.exp((difficulty - 400) / 400) + 0.5) if difficulty < 400 else round(difficulty)
        key = "atcoder:" + item["id"]
        problems[key] = {"id": key, "platform": "atcoder", "contestId": "atcoder:" + item["contest_id"], "index": item.get("problem_index", item["id"]), "name": item.get("name", item.get("title", item["id"])), "url": f"https://atcoder.jp/contests/{item['contest_id']}/tasks/{item['id']}", "difficulty": difficulty}
    contests = {}
    timestamp = int(time.time())
    for item in raw_contests:
        if item["start_epoch_second"] > timestamp:
            continue
        key = "atcoder:" + item["id"]
        contests[key] = {"id": key, "platform": "atcoder", "name": item["title"], "kind": atcoder_kind(item["id"]), "startEpoch": item["start_epoch_second"], "url": f"https://atcoder.jp/contests/{item['id']}", "problems": [], "problemIndices": {}, "catalogComplete": True, "hasSubmissions": False}
    for item in associations:
        contest = contests.get("atcoder:" + item["contest_id"])
        key = "atcoder:" + item["problem_id"]
        if contest and key in problems and key not in contest["problems"]:
            contest["problems"].append(key)
            contest["problemIndices"][key] = item.get("problem_index", problems[key]["index"])
    accepted, attempted = [], set()
    for item in submissions:
        key, contest_key = "atcoder:" + item["problem_id"], "atcoder:" + item["contest_id"]
        attempted.add(key)
        if key not in problems:
            problems[key] = {"id": key, "platform": "atcoder", "contestId": contest_key, "index": item["problem_id"].split("_")[-1].upper(), "name": item["problem_id"], "url": f"https://atcoder.jp/contests/{item['contest_id']}/tasks/{item['problem_id']}", "difficulty": None}
        if contest_key not in contests:
            contests[contest_key] = {"id": contest_key, "platform": "atcoder", "name": item["contest_id"], "kind": atcoder_kind(item["contest_id"]), "startEpoch": 0, "url": f"https://atcoder.jp/contests/{item['contest_id']}", "problems": [], "problemIndices": {}, "catalogComplete": False}
        if key not in contests[contest_key]["problems"]:
            contests[contest_key]["problems"].append(key)
            contests[contest_key]["catalogComplete"] = False
        contests[contest_key]["hasSubmissions"] = True
        if item["result"] == "AC":
            accepted.append({"id": item["id"], "platform": "atcoder", "problemId": key, "epoch": item["epoch_second"], "url": f"https://atcoder.jp/contests/{item['contest_id']}/submissions/{item['id']}"})
    old_profile = previous.get("profile", {}) if previous else {}
    profile = {"handle": HANDLE, "url": f"https://atcoder.jp/users/{HANDLE}", "rating": old_profile.get("rating"), "maxRating": old_profile.get("maxRating"), "rank": "Algorithm", "lastSuccess": old_profile.get("lastSuccess")}
    history = optional(client, f"https://atcoder.jp/users/{HANDLE}/history/json", None, warnings, "Rating 暂未更新，保留上次记录")
    if history is not None:
        rated = sorted((row for row in history if row.get("IsRated")), key=lambda row: row["EndTime"])
        profile.update(rating=rated[-1]["NewRating"] if rated else None, maxRating=max((row["NewRating"] for row in rated), default=None), lastSuccess=now())
    return make_snapshot("atcoder", problems, contests, accepted, attempted, profile, warnings, len(submissions))


def collect_codeforces(client, previous):
    warnings = []
    submissions = codeforces_submissions(client)
    print(f"Codeforces: {len(submissions)} submissions", flush=True)
    raw_problems = client.get(f"{CF}/api/problemset.problems?lang=en")["problems"]
    raw_contests = client.get(f"{CF}/api/contest.list?lang=en")
    raw_gyms = client.get(f"{CF}/api/contest.list?gym=true&lang=en")
    problems = {problem["id"]: problem for problem in map(cf_problem, raw_problems)}
    known_contests = {f"codeforces:{item['id']}": item for item in raw_contests + raw_gyms}
    contests = {}
    for item in raw_contests:
        if item.get("phase") != "FINISHED":
            continue
        key = f"codeforces:{item['id']}"
        contests[key] = {"id": key, "platform": "codeforces", "name": item["name"], "kind": codeforces_kind(item), "startEpoch": item.get("startTimeSeconds", 0), "url": f"{CF}/contest/{item['id']}", "problems": [], "catalogComplete": True, "hasSubmissions": False}
    for problem in problems.values():
        if problem["contestId"] in contests:
            contests[problem["contestId"]]["problems"].append(problem["id"])
    accepted, attempted = [], set()
    for item in submissions:
        problem = cf_problem(item["problem"])
        key, contest_key = problem["id"], problem["contestId"]
        attempted.add(key)
        if key not in problems:
            problems[key] = problem
        if contest_key and contest_key not in contests:
            info = known_contests.get(contest_key, {"id": item["problem"]["contestId"], "name": f"Codeforces {item['problem']['contestId']}"})
            route = "gym" if int(info["id"]) >= 100000 else "contest"
            contests[contest_key] = {"id": contest_key, "platform": "codeforces", "name": info["name"], "kind": codeforces_kind(info), "startEpoch": info.get("startTimeSeconds", 0), "url": f"{CF}/{route}/{info['id']}", "problems": [], "catalogComplete": False}
        if contest_key and key not in contests[contest_key]["problems"]:
            contests[contest_key]["problems"].append(key)
            contests[contest_key]["catalogComplete"] = False
        if contest_key:
            contests[contest_key]["hasSubmissions"] = True
        if item.get("verdict") == "OK":
            raw_id = item.get("contestId", item["problem"].get("contestId"))
            route = "gym" if raw_id and int(raw_id) >= 100000 else "contest"
            submission_url = f"{CF}/{route}/{raw_id}/submission/{item['id']}" if raw_id else f"{CF}/submission/{item['id']}"
            accepted.append({"id": item["id"], "platform": "codeforces", "problemId": key, "epoch": item["creationTimeSeconds"], "url": submission_url})
    old_contests = {item["id"]: item for item in previous.get("contests", [])} if previous else {}
    old_problems = {item["id"]: item for item in previous.get("problems", [])} if previous else {}
    missing_gyms = 0
    for contest in contests.values():
        if contest["kind"] != "Gym":
            continue
        old = old_contests.get(contest["id"])
        known = set(contest["problems"])
        if old and old["catalogComplete"] and known.issubset(old["problems"]):
            contest["problems"] = list(old["problems"])
            contest["catalogComplete"] = True
            for key in contest["problems"]:
                if key not in problems:
                    problems[key] = old_problems[key]
            continue
        raw_id = contest["id"].split(":")[1]
        print(f"Fetching public Gym problem table: {raw_id}", flush=True)
        try:
            gym_problems = parse_gym(client.get(f"{CF}/gym/{raw_id}?locale=en", as_json=False), raw_id)
            found = {problem["id"] for problem in gym_problems}
            if not found or not known.issubset(found):
                raise ValueError("Incomplete Gym problem table")
            contest["problems"] = [problem["id"] for problem in gym_problems]
            contest["catalogComplete"] = True
            for problem in gym_problems:
                if problem["id"] not in problems:
                    problems[problem["id"]] = problem
        except (RuntimeError, ValueError) as error:
            print(f"Warning: Gym {raw_id}: {error}", flush=True)
            missing_gyms += 1
    if missing_gyms:
        warnings.append(f"{missing_gyms} 场 Gym 的题目目录暂不完整，进度分母显示 ?")
    old_profile = previous.get("profile", {}) if previous else {}
    profile = {"handle": HANDLE, "url": f"{CF}/profile/{HANDLE}", "rating": old_profile.get("rating"), "maxRating": old_profile.get("maxRating"), "rank": old_profile.get("rank"), "lastSuccess": old_profile.get("lastSuccess")}
    info = optional(client, f"{CF}/api/user.info?handles={HANDLE}", None, warnings, "Rating 暂未更新，保留上次记录")
    if info is not None:
        profile.update(rating=info[0].get("rating"), maxRating=info[0].get("maxRating"), rank=info[0].get("rank"), lastSuccess=now())
    return make_snapshot("codeforces", problems, contests, accepted, attempted, profile, warnings, len(submissions))


def make_snapshot(platform, problems, contests, accepted, attempted, profile, warnings, submission_count):
    final_contests = [contest for contest in contests.values() if contest["problems"]]
    for contest in final_contests:
        contest["problems"].sort(key=lambda key: index_order(contest.get("problemIndices", {}).get(key, problems[key]["index"])))
    snapshot = {"schemaVersion": 1, "platform": platform, "handle": HANDLE, "lastSuccess": now(), "profile": profile, "warnings": warnings, "submissionCount": submission_count, "problems": sorted(problems.values(), key=lambda problem: problem["id"]), "contests": sorted(final_contests, key=lambda contest: contest["id"]), "accepted": sorted(accepted, key=lambda event: (event["epoch"], event["id"])), "attempted": sorted(attempted)}
    validate(snapshot)
    return snapshot


def validate(snapshot):
    if snapshot.get("schemaVersion") != 1 or snapshot.get("handle") != HANDLE:
        raise ValueError("Snapshot schema or handle mismatch")
    problems = {problem["id"] for problem in snapshot["problems"]}
    if len(problems) != len(snapshot["problems"]):
        raise ValueError("Duplicate problem identity")
    if len({event["id"] for event in snapshot["accepted"]}) != len(snapshot["accepted"]):
        raise ValueError("Duplicate accepted submission")
    if not problems or not snapshot["contests"]:
        raise ValueError("Unexpected empty problem or contest catalogue")
    for event in snapshot["accepted"]:
        if event["problemId"] not in problems or event["epoch"] <= 0:
            raise ValueError("Invalid accepted submission")
    if not set(snapshot["attempted"]).issubset(problems):
        raise ValueError("Attempted problem missing from catalogue")
    for contest in snapshot["contests"]:
        if len(set(contest["problems"])) != len(contest["problems"]) or not set(contest["problems"]).issubset(problems):
            raise ValueError("Invalid contest problem mapping")


def refresh_source(platform, collector, client, previous):
    try:
        snapshot = collector(client, previous)
        # Empty success responses should not erase an established history silently.
        if previous and previous["submissionCount"] > 0 and snapshot["submissionCount"] == 0:
            raise ValueError("Empty submission history after an established nonempty snapshot")
        return snapshot, None
    except Exception as error:
        if previous is None:
            raise RuntimeError(f"{platform}: first sync failed; no fallback snapshot exists: {error}") from error
        validate(previous)
        return copy.deepcopy(previous), str(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Build dashboard from existing source snapshots without requests")
    args = parser.parse_args()
    client, sources, snapshots, failed = Client(), {}, [], []
    for platform, collector in (("atcoder", collect_atcoder), ("codeforces", collect_codeforces)):
        path = SOURCE_DIR / f"{platform}.json"
        previous = read_json(path)
        if args.offline:
            if not previous:
                raise RuntimeError(f"Missing cached snapshot: {path}")
            snapshot, error = previous, None
            validate(snapshot)
        else:
            snapshot, error = refresh_source(platform, collector, client, previous)
            if error is None:
                atomic_json(path, snapshot)
        if error:
            failed.append(platform)
            print(f"::warning::{platform}: using previous snapshot. {error}", flush=True)
        source = {key: snapshot[key] for key in ("lastSuccess", "profile", "warnings", "submissionCount")}
        source["error"] = error
        sources[platform] = source
        snapshots.append(snapshot)
        count = len({event["problemId"] for event in snapshot["accepted"]})
        print(f"{platform}: {count} solved, {len(snapshot['accepted'])} AC submissions", flush=True)
    dashboard = {"schemaVersion": 1, "handle": HANDLE, "timezone": "Asia/Taipei", "generatedAt": now(), "sources": sources}
    for key in ("problems", "contests", "accepted", "attempted"):
        dashboard[key] = [item for snapshot in snapshots for item in snapshot[key]]
    atomic_json(OUTPUT, dashboard)
    summary = f"Lucius7: {len({event['problemId'] for event in dashboard['accepted']})} solved problems, {len(dashboard['accepted'])} AC submissions.\n"
    if failed:
        summary += f"Stale sources: {', '.join(failed)}. Previous successful snapshots retained.\n"
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as output:
            output.write(summary)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"degraded={'true' if failed else 'false'}\n")


if __name__ == "__main__":
    main()
