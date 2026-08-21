#!/usr/bin/env python3
"""Independently discover, inspect, rank, and render useful Agent Skill files.

This crawler does not parse an upstream awesome-list. It searches GitHub repositories,
opens each repository's pinned tree, fetches actual SKILL.md files, parses their
frontmatter, applies quality/usefulness heuristics, and emits a traceable catalog.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

API = "https://api.github.com"
RECORD_TYPE = "direct-skill-file"
DISCOVERY_METHOD = "road-of-flower-direct-github-scan"
INSTALL_STATUS = "not-installed"
VERIFY_STATUS = "direct-file-fetched-frontmatter-parsed-not-audited"
DEFAULT_CONFIG = Path(__file__).with_name("direct_sources.json")
OUTPUT_SUBDIR = Path("skills/direct")
MIN_DESCRIPTION = 24
MAX_REPOSITORIES = 90
MAX_FILES_TO_FETCH = 950
DEFAULT_MAX_PER_REPO = 45

FIELDS = [
    "id", "name", "description", "category", "publisher", "repository", "path",
    "url", "source_commit", "repo_stars", "repo_pushed_at", "repo_license",
    "source_tier", "usefulness_score", "usefulness_tier", "skill_license",
    "compatibility", "frontmatter", "overlap_with_imported", "discovered_via",
    "record_type", "install_status", "verification_status", "indexed_at",
]

TIER_POINTS = {
    "official": 34,
    "scientific": 28,
    "maintainer": 25,
    "community": 17,
    "discovered": 10,
}
TIER_ORDER = {"official": 0, "scientific": 1, "maintainer": 2, "community": 3, "discovered": 4}

CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Security & Safety", ("security", "secure", "vulnerability", "threat", "audit", "privacy", "safety", "owasp", "red team", "guardrail")),
    ("Testing & Quality", ("test", "testing", "qa", "quality", "lint", "review", "review-pr", "pr review", "pull request review", "code review", "debug", "troubleshoot", "verification", "benchmark", "eval")),
    ("Research & Science", ("research", "scientific", "paper", "literature", "hypothesis", "bio", "chem", "physics", "genomic", "clinical", "statistics", "experiment", "citation")),
    ("AI & Machine Learning", ("machine learning", "deep learning", "llm", "model", "huggingface", "embedding", "training", "fine-tun", "inference", "rag", "vision", "multimodal")),
    ("Agent Engineering", ("agent", "skill creator", "context engineering", "memory", "handoff", "workflow", "orchestration", "prompt", "mcp", "tool use")),
    ("Data & Databases", ("data", "database", "sql", "postgres", "redis", "mongodb", "etl", "analytics", "warehouse", "vector", "spreadsheet", "csv")),
    ("DevOps & Cloud", ("devops", "deploy", "deployment", "cloud", "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "observability", "sre")),
    ("Web & Frontend", ("frontend", "web", "react", "next.js", "nextjs", "vue", "angular", "css", "html", "accessibility", "browser", "playwright", "performance")),
    ("Backend & APIs", ("backend", "api", "server", "service", "python", "golang", "go ", "rust", "java", ".net", "typescript", "node", "graphql")),
    ("Documents & Knowledge", ("document", "pdf", "docx", "slides", "ppt", "writing", "technical writing", "documentation", "knowledge", "obsidian", "notion", "markdown")),
    ("Product & Design", ("product", "design", "ux", "ui", "figma", "customer", "market", "roadmap", "requirements", "prototype")),
    ("Collaboration & Productivity", ("github", "pull request", "issue", "planning", "project", "meeting", "email", "calendar", "collaboration", "productivity", "release")),
    ("Media & Creative", ("image", "video", "audio", "animation", "gsap", "visual", "creative", "remotion", "canvas", "art")),
    ("Business & Operations", ("business", "finance", "sales", "marketing", "operations", "legal", "compliance", "strategy", "advertising")),
]
GENERAL_UTILITY_TERMS = (
    "test", "debug", "review", "document", "research", "security", "data", "deploy",
    "browser", "pdf", "spreadsheet", "slides", "git", "github", "database", "api",
    "frontend", "backend", "machine learning", "evaluation", "agent", "workflow",
    "writing", "product", "design", "cloud", "docker", "kubernetes", "planning",
    "analysis", "automation", "monitor", "accessibility", "performance", "release",
)
EXCLUDED_PATH_FRAGMENTS = (
    "/node_modules/", "/vendor/", "/fixtures/", "/fixture/", "/testdata/",
    "/tests/fixtures/", "/examples/", "/example/", "/templates/", "/template/",
    "/archive/", "/deprecated/", "/dist/", "/build/",
)
EXCLUDED_TEXT = (
    "credential theft", "steal credentials", "phishing campaign", "malware",
    "ransomware", "keylogger", "password cracking", "bypass authentication",
    "evade detection", "spam automation", "mass unsolicited", "casino", "gambling",
)
DEFENSIVE_TEXT = ("defensive", "detection", "audit", "mitigation", "secure", "security review", "incident response")
LOW_VALUE_NAMES = {"skill", "template", "example", "demo", "sample", "test", "placeholder"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.S)
HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)
SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class RepoSpec:
    repository: str
    tier: str
    reason: str
    max_items: int


@dataclass
class RepoSnapshot:
    full_name: str
    owner_type: str
    stars: int
    forks: int
    pushed_at: str
    updated_at: str
    default_branch: str
    commit_sha: str
    license: str
    tier: str
    reason: str
    max_items: int
    skill_paths: list[str]
    discovered_by: str


class GithubClient:
    def __init__(self, token: str | None, *, timeout: int = 45, retries: int = 5) -> None:
        self.token = token or ""
        self.timeout = timeout
        self.retries = retries

    def _request(self, url: str) -> bytes:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "RoadOfFlower-Direct-Skill-Research/2.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read()
            except urllib.error.HTTPError as exc:
                last = exc
                if exc.code in {403, 429, 500, 502, 503, 504} and attempt + 1 < self.retries:
                    retry_after = exc.headers.get("Retry-After")
                    delay = int(retry_after) if retry_after and retry_after.isdigit() else min(2 ** attempt, 20)
                    time.sleep(delay)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last = exc
                if attempt + 1 < self.retries:
                    time.sleep(min(2 ** attempt, 20))
                    continue
                raise
        raise RuntimeError(f"request failed: {url}: {last}")

    def json(self, url: str) -> Any:
        return json.loads(self._request(url).decode("utf-8"))

    def search_repositories(self, query: str, *, per_page: int = 100) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": per_page})
        payload = self.json(f"{API}/search/repositories?{params}")
        return list(payload.get("items") or [])

    def repository(self, full_name: str) -> dict[str, Any]:
        return dict(self.json(f"{API}/repos/{full_name}"))

    def commit_sha(self, full_name: str, ref: str) -> str:
        payload = self.json(f"{API}/repos/{full_name}/commits/{urllib.parse.quote(ref, safe='')}")
        return str(payload["sha"])

    def recursive_tree(self, full_name: str, sha: str) -> dict[str, Any]:
        return dict(self.json(f"{API}/repos/{full_name}/git/trees/{sha}?recursive=1"))

    def file_text(self, full_name: str, path: str, sha: str) -> str:
        quoted = urllib.parse.quote(path, safe="/")
        payload = self.json(f"{API}/repos/{full_name}/contents/{quoted}?ref={sha}")
        if payload.get("type") != "file" or payload.get("encoding") != "base64":
            raise ValueError(f"not a base64 file: {full_name}:{path}")
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")


def clean_text(value: str) -> str:
    value = str(value or "").strip().strip('"\'')
    return SPACE_RE.sub(" ", value).strip()


def slugify(value: str) -> str:
    return NON_ALNUM_RE.sub("-", clean_text(value).casefold()).strip("-") or "skill"


def normalized_name(value: str) -> str:
    value = clean_text(value).casefold()
    value = re.sub(r"\b(agent|claude|codex)\b", " ", value)
    return SPACE_RE.sub(" ", NON_ALNUM_RE.sub(" ", value)).strip()


def parse_frontmatter(text: str) -> tuple[dict[str, str], bool]:
    match = FRONTMATTER_RE.search(text)
    if not match:
        return {}, False
    lines = match.group(1).splitlines()
    result: dict[str, str] = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            i += 1
            continue
        key, value = raw.split(":", 1)
        key = key.strip().casefold().replace("-", "_")
        value = value.strip()
        if value in {">", ">-", "|", "|-"}:
            i += 1
            chunks: list[str] = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                if lines[i].strip():
                    chunks.append(lines[i].strip())
                i += 1
            result[key] = clean_text(" ".join(chunks))
            continue
        result[key] = clean_text(value)
        i += 1
    return result, True


def fallback_description(text: str) -> str:
    body = FRONTMATTER_RE.sub("", text, count=1).strip()
    body = re.sub(r"```.*?```", " ", body, flags=re.S)
    paragraphs = [clean_text(p.replace("\n", " ")) for p in re.split(r"\n\s*\n", body)]
    for paragraph in paragraphs:
        if paragraph.startswith("#"):
            continue
        paragraph = re.sub(r"^[>*-]+\s*", "", paragraph)
        if len(paragraph) >= MIN_DESCRIPTION:
            return paragraph[:700]
    return ""


def parse_skill(text: str, path: str) -> dict[str, Any] | None:
    meta, has_frontmatter = parse_frontmatter(text)
    fallback_name = Path(path).parent.name if Path(path).name.casefold() == "skill.md" else Path(path).stem
    heading = HEADING_RE.search(FRONTMATTER_RE.sub("", text, count=1))
    name = clean_text(meta.get("name") or (heading.group(1) if heading else fallback_name))
    description = clean_text(meta.get("description") or fallback_description(text))
    if normalized_name(name) in LOW_VALUE_NAMES or len(description) < MIN_DESCRIPTION:
        return None
    return {
        "name": name[:180],
        "description": description[:900],
        "skill_license": clean_text(meta.get("license", ""))[:120],
        "compatibility": clean_text(meta.get("compatibility", ""))[:300],
        "frontmatter": "yes" if has_frontmatter else "no",
    }


def path_is_candidate(path: str) -> bool:
    lower = "/" + path.casefold().lstrip("/")
    if not lower.endswith("/skill.md") and lower != "/skill.md":
        return False
    if any(fragment in lower for fragment in EXCLUDED_PATH_FRAGMENTS):
        return False
    return True


def path_priority(path: str) -> int:
    lower = path.casefold()
    score = 0
    if "/skills/" in "/" + lower:
        score += 8
    if "/.agents/skills/" in "/" + lower or "/.claude/skills/" in "/" + lower:
        score += 7
    if lower.count("/") <= 4:
        score += 4
    for term in GENERAL_UTILITY_TERMS:
        if term.replace(" ", "-") in lower or term.replace(" ", "_") in lower:
            score += 1
    return score


def infer_category(name: str, description: str, path: str) -> str:
    hay = f"{name} {description} {path}".casefold().replace("-", " ").replace("_", " ")
    scores: list[tuple[int, int, str]] = []
    for index, (category, keywords) in enumerate(CATEGORY_RULES):
        value = sum(2 if keyword in name.casefold() else 1 for keyword in keywords if keyword in hay)
        scores.append((value, -index, category))
    best = max(scores)
    return best[2] if best[0] > 0 else "Specialized & Other"


def dangerous(name: str, description: str) -> bool:
    hay = f"{name} {description}".casefold()
    harmful = any(term in hay for term in EXCLUDED_TEXT)
    defensive = any(term in hay for term in DEFENSIVE_TEXT)
    return harmful and not defensive


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def source_tier(spec: RepoSpec | None) -> str:
    return spec.tier if spec else "discovered"


def repo_quality(repo: dict[str, Any], tier: str) -> float:
    stars = int(repo.get("stargazers_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    value = TIER_POINTS.get(tier, 8)
    value += min(16.0, math.log10(stars + 1) * 6.0)
    value += min(4.0, math.log10(forks + 1) * 2.0)
    if str(repo.get("owner", {}).get("type") or "").casefold() == "organization":
        value += 3
    if repo.get("license"):
        value += 2
    pushed = parse_time(str(repo.get("pushed_at") or ""))
    if pushed:
        age_days = max(0, (datetime.now(timezone.utc) - pushed).days)
        value += max(0.0, 8.0 - age_days / 180.0)
    if repo.get("archived"):
        value -= 100
    if repo.get("fork"):
        value -= 12
    return value


def usefulness_score(skill: dict[str, Any], snapshot: RepoSnapshot) -> int:
    name = skill["name"]
    description = skill["description"]
    path = skill["path"]
    hay = f"{name} {description} {path}".casefold().replace("-", " ").replace("_", " ")
    score = float(TIER_POINTS.get(snapshot.tier, 8))
    score += min(16.0, math.log10(snapshot.stars + 1) * 6.0)
    pushed = parse_time(snapshot.pushed_at)
    if pushed:
        age_days = max(0, (datetime.now(timezone.utc) - pushed).days)
        score += max(0.0, 8.0 - age_days / 180.0)
    if skill.get("frontmatter") == "yes":
        score += 9
    if 45 <= len(description) <= 650:
        score += 8
    elif len(description) > 650:
        score += 5
    if any(phrase in hay for phrase in ("use when", "when to use", "use this", "适用", "用于")):
        score += 3
    utility_hits = sum(1 for term in GENERAL_UTILITY_TERMS if term in hay)
    score += min(18, utility_hits * 2)
    category = infer_category(name, description, path)
    if category in {"Testing & Quality", "Research & Science", "Security & Safety", "Agent Engineering", "Documents & Knowledge", "Data & Databases"}:
        score += 3
    if skill.get("skill_license") or snapshot.license:
        score += 2
    if skill.get("compatibility"):
        score += 2
    if normalized_name(name) in {"readme", "overview", "general", "helper", "utils", "utility"}:
        score -= 12
    if "deprecated" in hay or "legacy" in hay:
        score -= 10
    return max(0, min(100, int(round(score))))


def usefulness_tier(score: int) -> str:
    if score >= 80:
        return "essential"
    if score >= 68:
        return "high"
    if score >= 54:
        return "useful"
    return "specialized"


def load_config(path: Path) -> tuple[dict[str, Any], dict[str, RepoSpec]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    specs: dict[str, RepoSpec] = {}
    for item in payload.get("repositories", []):
        full = str(item["repository"])
        specs[full.casefold()] = RepoSpec(
            repository=full,
            tier=str(item.get("tier") or "community"),
            reason=str(item.get("reason") or "seeded direct source"),
            max_items=int(item.get("max_items") or DEFAULT_MAX_PER_REPO),
        )
    return payload, specs


def discover_repo_metadata(client: GithubClient, config: dict[str, Any], specs: dict[str, RepoSpec]) -> dict[str, dict[str, Any]]:
    repos: dict[str, dict[str, Any]] = {}
    for query in config.get("search_queries", []):
        try:
            for repo in client.search_repositories(str(query), per_page=100):
                full = str(repo.get("full_name") or "")
                if full:
                    repo["_discovered_by"] = f"github-search:{query}"
                    repos.setdefault(full.casefold(), repo)
        except Exception as exc:  # continue broad research if one query fails
            print(f"warning: search query failed: {query}: {exc}", file=sys.stderr)
    missing = [spec for key, spec in specs.items() if key not in repos]
    if missing:
        with ThreadPoolExecutor(max_workers=8) as pool:
            future_map = {pool.submit(client.repository, spec.repository): spec for spec in missing}
            for future in as_completed(future_map):
                spec = future_map[future]
                try:
                    repo = future.result()
                    repo["_discovered_by"] = "seeded-direct-source"
                    repos[spec.repository.casefold()] = repo
                except Exception as exc:
                    print(f"warning: seeded repository unavailable: {spec.repository}: {exc}", file=sys.stderr)
    ranked = sorted(
        repos.values(),
        key=lambda repo: (
            -repo_quality(repo, source_tier(specs.get(str(repo.get("full_name") or "").casefold()))),
            str(repo.get("full_name") or "").casefold(),
        ),
    )
    return {str(repo["full_name"]).casefold(): repo for repo in ranked[:MAX_REPOSITORIES]}


def snapshot_repository(client: GithubClient, repo: dict[str, Any], spec: RepoSpec | None) -> RepoSnapshot | None:
    full = str(repo.get("full_name") or "")
    if not full or repo.get("archived") or repo.get("disabled"):
        return None
    default_branch = str(repo.get("default_branch") or "main")
    try:
        sha = client.commit_sha(full, default_branch)
        tree = client.recursive_tree(full, sha)
    except Exception as exc:
        print(f"warning: cannot inspect repository tree: {full}: {exc}", file=sys.stderr)
        return None
    paths = [
        str(item.get("path"))
        for item in tree.get("tree", [])
        if item.get("type") == "blob" and path_is_candidate(str(item.get("path") or ""))
    ]
    if not paths:
        return None
    paths = sorted(set(paths), key=lambda p: (-path_priority(p), p.casefold()))
    limit = min(len(paths), max((spec.max_items if spec else DEFAULT_MAX_PER_REPO) * 2, 25), 90)
    license_info = repo.get("license") or {}
    return RepoSnapshot(
        full_name=full,
        owner_type=str(repo.get("owner", {}).get("type") or ""),
        stars=int(repo.get("stargazers_count") or 0),
        forks=int(repo.get("forks_count") or 0),
        pushed_at=str(repo.get("pushed_at") or ""),
        updated_at=str(repo.get("updated_at") or ""),
        default_branch=default_branch,
        commit_sha=sha,
        license=str(license_info.get("spdx_id") or "NOASSERTION"),
        tier=source_tier(spec),
        reason=spec.reason if spec else "discovered through independent GitHub repository search",
        max_items=spec.max_items if spec else DEFAULT_MAX_PER_REPO,
        skill_paths=paths[:limit],
        discovered_by=str(repo.get("_discovered_by") or "github-search"),
    )


def inspect_repositories(client: GithubClient, repos: dict[str, dict[str, Any]], specs: dict[str, RepoSpec]) -> list[RepoSnapshot]:
    snapshots: list[RepoSnapshot] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        future_map = {
            pool.submit(snapshot_repository, client, repo, specs.get(key)): key
            for key, repo in repos.items()
        }
        for future in as_completed(future_map):
            try:
                snapshot = future.result()
                if snapshot:
                    snapshots.append(snapshot)
            except Exception as exc:
                print(f"warning: repository inspection failed: {future_map[future]}: {exc}", file=sys.stderr)
    return sorted(snapshots, key=lambda s: (TIER_ORDER.get(s.tier, 9), -s.stars, s.full_name.casefold()))


def load_imported_names(root: Path) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    urls: set[str] = set()
    path = root / "skills" / "catalog.csv"
    if not path.exists():
        return names, urls
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            names.add(normalized_name(row.get("name", "")))
            urls.add(str(row.get("url") or "").rstrip("/"))
    return names, urls


def inspect_skill(client: GithubClient, snapshot: RepoSnapshot, path: str, imported_names: set[str], imported_urls: set[str]) -> dict[str, Any] | None:
    try:
        text = client.file_text(snapshot.full_name, path, snapshot.commit_sha)
    except Exception as exc:
        print(f"warning: cannot fetch Skill file: {snapshot.full_name}:{path}: {exc}", file=sys.stderr)
        return None
    parsed = parse_skill(text, path)
    if not parsed or dangerous(parsed["name"], parsed["description"]):
        return None
    parsed["path"] = path
    score = usefulness_score(parsed, snapshot)
    if score < 38:
        return None
    url = f"https://github.com/{snapshot.full_name}/blob/{snapshot.commit_sha}/{urllib.parse.quote(path, safe='/')}"
    overlap = "yes" if normalized_name(parsed["name"]) in imported_names or url.rstrip("/") in imported_urls else "no"
    identity = f"{snapshot.full_name}:{path}:{snapshot.commit_sha}".encode("utf-8")
    return {
        "id": "direct-" + hashlib.sha1(identity).hexdigest()[:14],
        "name": parsed["name"],
        "description": parsed["description"],
        "category": infer_category(parsed["name"], parsed["description"], path),
        "publisher": snapshot.full_name.split("/", 1)[0],
        "repository": snapshot.full_name,
        "path": path,
        "url": url,
        "source_commit": snapshot.commit_sha,
        "repo_stars": str(snapshot.stars),
        "repo_pushed_at": snapshot.pushed_at,
        "repo_license": snapshot.license,
        "source_tier": snapshot.tier,
        "usefulness_score": str(score),
        "usefulness_tier": usefulness_tier(score),
        "skill_license": parsed["skill_license"],
        "compatibility": parsed["compatibility"],
        "frontmatter": parsed["frontmatter"],
        "overlap_with_imported": overlap,
        "discovered_via": snapshot.discovered_by,
        "record_type": RECORD_TYPE,
        "install_status": INSTALL_STATUS,
        "verification_status": VERIFY_STATUS,
        "indexed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def gather_skills(client: GithubClient, snapshots: list[RepoSnapshot], root: Path) -> list[dict[str, Any]]:
    imported_names, imported_urls = load_imported_names(root)
    tasks: list[tuple[RepoSnapshot, str]] = []
    # First preserve breadth: at least a few paths from every direct source.
    for snapshot in snapshots:
        for path in snapshot.skill_paths[: min(len(snapshot.skill_paths), 8)]:
            tasks.append((snapshot, path))
    seen = {(s.full_name.casefold(), p) for s, p in tasks}
    remaining: list[tuple[int, RepoSnapshot, str]] = []
    for snapshot in snapshots:
        for path in snapshot.skill_paths:
            key = (snapshot.full_name.casefold(), path)
            if key not in seen:
                remaining.append((path_priority(path), snapshot, path))
    remaining.sort(key=lambda item: (-item[0], TIER_ORDER.get(item[1].tier, 9), -item[1].stars, item[1].full_name.casefold(), item[2]))
    for _, snapshot, path in remaining:
        if len(tasks) >= MAX_FILES_TO_FETCH:
            break
        tasks.append((snapshot, path))
    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        future_map = {
            pool.submit(inspect_skill, client, snapshot, path, imported_names, imported_urls): (snapshot.full_name, path)
            for snapshot, path in tasks
        }
        for future in as_completed(future_map):
            try:
                record = future.result()
                if record:
                    records.append(record)
            except Exception as exc:
                repo, path = future_map[future]
                print(f"warning: skill inspection failed: {repo}:{path}: {exc}", file=sys.stderr)
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (record["repository"].casefold(), normalized_name(record["name"]))
        current = deduped.get(key)
        if not current or int(record["usefulness_score"]) > int(current["usefulness_score"]):
            deduped[key] = record
    return list(deduped.values())


def select_diverse(records: list[dict[str, Any]], snapshots: list[RepoSnapshot], target: int) -> list[dict[str, Any]]:
    cap_by_repo = {s.full_name.casefold(): s.max_items for s in snapshots}
    queues: dict[str, deque[dict[str, Any]]] = {}
    for repo, items in _group(records, "repository").items():
        ordered = sorted(items, key=_record_sort_key)
        queues[repo.casefold()] = deque(ordered[: cap_by_repo.get(repo.casefold(), DEFAULT_MAX_PER_REPO)])
    repo_order = sorted(
        queues,
        key=lambda repo: (
            TIER_ORDER.get(queues[repo][0]["source_tier"], 9),
            -int(queues[repo][0]["repo_stars"]),
            repo,
        ),
    )
    selected: list[dict[str, Any]] = []
    # breadth floor
    for repo in repo_order:
        for _ in range(min(5, len(queues[repo]))):
            selected.append(queues[repo].popleft())
            if len(selected) >= target:
                return sorted(selected, key=_record_sort_key)
    # score-aware round robin
    while len(selected) < target and any(queues.values()):
        active = sorted(
            (repo for repo in repo_order if queues[repo]),
            key=lambda repo: (-int(queues[repo][0]["usefulness_score"]), repo),
        )
        if not active:
            break
        for repo in active:
            selected.append(queues[repo].popleft())
            if len(selected) >= target:
                break
    return sorted(selected, key=_record_sort_key)


def select_featured(records: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    repo_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    featured: list[dict[str, Any]] = []
    for record in sorted(records, key=_record_sort_key):
        repo = record["repository"]
        category = record["category"]
        if repo_counts[repo] >= 25 or category_counts[category] >= 42:
            continue
        featured.append(record)
        repo_counts[repo] += 1
        category_counts[category] += 1
        if len(featured) >= target:
            break
    if len(featured) < target:
        chosen = {r["id"] for r in featured}
        for record in sorted(records, key=_record_sort_key):
            if record["id"] not in chosen:
                featured.append(record)
                chosen.add(record["id"])
                if len(featured) >= target:
                    break
    return featured


def _record_sort_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (-int(record["usefulness_score"]), TIER_ORDER.get(record["source_tier"], 9), record["category"].casefold(), record["name"].casefold(), record["url"])


def _group(records: Iterable[dict[str, Any]], field: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record[field])].append(record)
    return dict(grouped)


def markdown_escape(value: str) -> str:
    return clean_text(value).replace("|", "\\|")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def render_index(records: list[dict[str, Any]], title: str, intro: str) -> str:
    lines = [f"# {title}", "", intro, "", f"共 **{len(records):,}** 条；按 RoadOfFlower 实用性评分排序。", ""]
    by_category = _group(records, "category")
    for category in sorted(by_category):
        items = sorted(by_category[category], key=_record_sort_key)
        lines += [f"## {category}（{len(items)}）", "", "| 分数 | Skill | 来源 | 简介 |", "|---:|---|---|---|"]
        for row in items:
            lines.append(
                f"| {row['usefulness_score']} | [{markdown_escape(row['name'])}]({row['url']}) | "
                f"`{row['repository']}` · {row['source_tier']} | {markdown_escape(row['description'][:240])} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_sources(snapshots: list[RepoSnapshot], selected: list[dict[str, Any]]) -> str:
    counts = Counter(row["repository"] for row in selected)
    lines = [
        "# 直接检索来源",
        "",
        "本页记录 RoadOfFlower 自己直接检查的 GitHub 仓库。同步器读取固定提交的仓库树和实际 `SKILL.md` 文件；它不从其他 awesome-list 复制条目。",
        "",
        "| 仓库 | 层级 | Stars | 固定提交 | 入选 | 发现方式 | 选择理由 |",
        "|---|---|---:|---|---:|---|---|",
    ]
    for s in snapshots:
        if not counts[s.full_name]:
            continue
        lines.append(
            f"| [{s.full_name}](https://github.com/{s.full_name}/tree/{s.commit_sha}) | {s.tier} | {s.stars} | "
            f"`{s.commit_sha[:12]}` | {counts[s.full_name]} | {markdown_escape(s.discovered_by)} | {markdown_escape(s.reason)} |"
        )
    lines += [
        "",
        "## 边界",
        "",
        "- `official` 表示仓库所有者与产品/组织关系较明确，不代表 RoadOfFlower 与其合作。",
        "- `scientific`、`maintainer`、`community` 是来源组织方式，不是安全评分。",
        "- 文件存在、可解析和来源可追溯，不等于代码安全、持续维护、跨客户端兼容或适合生产。",
    ]
    return "\n".join(lines)


def render_readme(records: list[dict[str, Any]], featured: list[dict[str, Any]], snapshots: list[RepoSnapshot], metadata: dict[str, Any]) -> str:
    categories = len({r["category"] for r in records})
    repos = len({r["repository"] for r in records})
    official = sum(1 for r in records if r["source_tier"] == "official")
    non_overlap = sum(1 for r in records if r["overlap_with_imported"] == "no")
    return f"""# RoadOfFlower 独立直连 Skill 索引

> 不是搬运另一张清单，而是直接进入原始仓库、读取固定提交中的实际 `SKILL.md`，再按实用性与来源多样性筛选。

## 当前结果

- 直接读取并入选：**{len(records):,} 条实际 Skill 文件**。
- 精选起步集：**{len(featured):,} 条**。
- 来源仓库：**{repos} 个**；应用分类：**{categories} 个**。
- 其中官方来源记录：**{official} 条**。
- 与原 1,200 条聚合索引按名称未重合：**{non_overlap} 条**。
- 研究批次：`{metadata['run_id']}`。

## 方法

1. 用多组 GitHub Repository Search 查询发现候选仓库；
2. 加入一组人工选择的官方、科学和维护者仓库，避免只按 stars 排名；
3. 固定每个仓库的 commit SHA，递归查找实际 `SKILL.md`；
4. 读取文件内容，解析 `name`、`description`、许可和兼容性字段；
5. 排除模板、示例、废弃项和明显恶意用途；
6. 根据来源、活跃度、元数据完整度、通用价值和任务清晰度评分；
7. 设置单仓库上限并轮询选取，防止一个大型集合垄断目录。

## 入口

- [完整直连索引](./INDEX.md)
- [精选 300](./USEFUL_300.md)
- [来源与固定提交](./SOURCES.md)
- [RoadOfFlower 独立检索与筛选方法](../../docs/07-independent-skill-research.md)
- [CSV](./catalog.csv) · [JSON](./catalog.json) · [元数据](./metadata.json)

## 状态含义

每条记录统一标记：

- `record_type={RECORD_TYPE}`
- `install_status={INSTALL_STATUS}`
- `verification_status={VERIFY_STATUS}`

这证明 RoadOfFlower 在本批次直接取得并解析了目标文件；不证明它已经安装、执行、安全审计或适用于你的环境。
"""


def update_root_readme(root: Path, records: list[dict[str, Any]], featured: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8") if path.exists() else "# RoadOfFlower · Agent Skill 花路\n"
    start = "<!-- direct-index:start -->"
    end = "<!-- direct-index:end -->"
    block = f"""{start}
## RoadOfFlower 自主检索层

除了固定版本的 1,200 条聚合索引，本项目还直接搜索 GitHub、检查原始仓库树并读取实际 `SKILL.md`：

- **{len(records):,} 条独立直连记录**，来自 **{metadata['repository_count']} 个仓库**；
- **{len(featured):,} 条高实用性起步集**；
- 每条都固定到具体 commit，并记录来源、路径、评分和未审计边界；
- 入口：[独立直连索引](skills/direct/INDEX.md) · [精选 300](skills/direct/USEFUL_300.md) · [直接来源](skills/direct/SOURCES.md)。

这层目录由 RoadOfFlower 自己执行检索、文件解析、评分和多样性选择，不依赖单一聚合清单。
{end}"""
    if start in text and end in text:
        text = re.sub(re.escape(start) + r".*?" + re.escape(end), block, text, flags=re.S)
    else:
        anchor = "## 快速入口"
        if anchor in text:
            text = text.replace(anchor, block + "\n\n" + anchor, 1)
        else:
            text += "\n\n" + block + "\n"
    if "| 浏览独立直连索引 |" not in text:
        row = "| 浏览独立直连索引 | [skills/direct/INDEX.md](skills/direct/INDEX.md) · [精选 300](skills/direct/USEFUL_300.md) |\n"
        marker = "| 浏览完整索引 |"
        pos = text.find(marker)
        if pos >= 0:
            line_end = text.find("\n", pos)
            text = text[: line_end + 1] + row + text[line_end + 1 :]
    if "| 张明（zmz2）的愿望 |" not in text:
        row = "| 张明（zmz2）的愿望 | [wish/zmz2/README.md](wish/zmz2/README.md) |\n"
        marker = "| 验证与风险 |"
        pos = text.find(marker)
        if pos >= 0:
            line_end = text.find("\n", pos)
            text = text[: line_end + 1] + row + text[line_end + 1 :]
    contribution = """<!-- wish-contribution:start -->
## 个人愿望区

Skill 与 Agent 教程仍是仓库主线。贡献者也可以在 `wish/<GitHub账号>/` 留下自己的愿望、路线图和祝福；个人内容不计入 Skill 数量。当前入口：[wish/zmz2](wish/zmz2/README.md)。
<!-- wish-contribution:end -->"""
    ws, we = "<!-- wish-contribution:start -->", "<!-- wish-contribution:end -->"
    if ws in text and we in text:
        text = re.sub(re.escape(ws) + r".*?" + re.escape(we), contribution, text, flags=re.S)
    else:
        anchor = "## 贡献与许可证"
        text = text.replace(anchor, contribution + "\n\n" + anchor, 1) if anchor in text else text + "\n\n" + contribution
    write_text(path, text)


def write_outputs(root: Path, selected: list[dict[str, Any]], featured: list[dict[str, Any]], snapshots: list[RepoSnapshot], config: dict[str, Any]) -> dict[str, Any]:
    out = root / OUTPUT_SUBDIR
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + hashlib.sha1("|".join(r["source_commit"] for r in selected[:40]).encode()).hexdigest()[:10]
    metadata = {
        "record_type": RECORD_TYPE,
        "record_count": len(selected),
        "featured_count": len(featured),
        "repository_count": len({r["repository"] for r in selected}),
        "category_count": len({r["category"] for r in selected}),
        "publisher_count": len({r["publisher"] for r in selected}),
        "official_record_count": sum(1 for r in selected if r["source_tier"] == "official"),
        "non_overlap_name_count": sum(1 for r in selected if r["overlap_with_imported"] == "no"),
        "discovery_method": DISCOVERY_METHOD,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "install_status": INSTALL_STATUS,
        "verification_status": VERIFY_STATUS,
        "search_queries": config.get("search_queries", []),
        "source_repositories": sorted({r["repository"] for r in selected}),
        "score_distribution": dict(sorted(Counter(r["usefulness_tier"] for r in selected).items())),
        "category_distribution": dict(sorted(Counter(r["category"] for r in selected).items())),
    }
    with (out / "catalog.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in FIELDS} for row in selected])
    write_text(out / "catalog.json", json.dumps({"metadata": metadata, "records": selected}, ensure_ascii=False, indent=2))
    write_text(out / "metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    write_text(out / "README.md", render_readme(selected, featured, snapshots, metadata))
    write_text(out / "INDEX.md", render_index(selected, "独立直连 Skill 完整索引", "每条记录来自 RoadOfFlower 对固定 GitHub 提交中实际 `SKILL.md` 的直接读取。"))
    write_text(out / "USEFUL_300.md", render_index(featured, "最有用的 300 条 Agent Skill 起步集", "该列表按通用价值、任务清晰度、来源、活跃度和多样性启发式排序；不是安全认证。"))
    write_text(out / "SOURCES.md", render_sources(snapshots, selected))
    category_dir = out / "categories"
    if category_dir.exists():
        for old in category_dir.glob("*.md"):
            old.unlink()
    for category, rows in _group(selected, "category").items():
        write_text(category_dir / f"{slugify(category)}.md", render_index(rows, category, "RoadOfFlower 独立直连目录的分类页。"))
    update_root_readme(root, selected, featured, metadata)
    return metadata


def validate_result(selected: list[dict[str, Any]], metadata: dict[str, Any], config: dict[str, Any]) -> None:
    minimum = int(config.get("minimum_count") or 350)
    min_repositories = int(config.get("minimum_repositories") or 15)
    errors: list[str] = []
    if len(selected) < minimum:
        errors.append(f"expected at least {minimum} direct Skill files, found {len(selected)}")
    repos = {r["repository"] for r in selected}
    if len(repos) < min_repositories:
        errors.append(f"expected at least {min_repositories} repositories, found {len(repos)}")
    ids = [r["id"] for r in selected]
    urls = [r["url"] for r in selected]
    if len(ids) != len(set(ids)):
        errors.append("duplicate IDs")
    if len(urls) != len(set(urls)):
        errors.append("duplicate URLs")
    for row in selected:
        if not re.search(r"/blob/[0-9a-f]{40}/(?:.+/)?SKILL\.md$", row["url"], re.I):
            errors.append(f"not commit-pinned SKILL.md URL: {row['url']}")
            break
        if row["record_type"] != RECORD_TYPE or row["verification_status"] != VERIFY_STATUS:
            errors.append(f"truth-boundary mismatch: {row['id']}")
            break
    if metadata["record_count"] != len(selected):
        errors.append("metadata record count mismatch")
    if errors:
        raise RuntimeError("; ".join(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--target", type=int)
    parser.add_argument("--featured", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    config, specs = load_config(args.config)
    target = args.target or int(config.get("target_count") or 500)
    featured_target = args.featured or int(config.get("featured_count") or 300)
    client = GithubClient(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    repos = discover_repo_metadata(client, config, specs)
    snapshots = inspect_repositories(client, repos, specs)
    print(f"inspected {len(snapshots)} repositories containing SKILL.md")
    candidates = gather_skills(client, snapshots, root)
    print(f"parsed {len(candidates)} quality-filtered direct Skill files")
    selected = select_diverse(candidates, snapshots, target)
    featured = select_featured(selected, min(featured_target, len(selected)))
    metadata = write_outputs(root, selected, featured, snapshots, config)
    validate_result(selected, metadata, config)
    print(
        f"PASS: {len(selected)} direct Skill files, {metadata['repository_count']} repositories, "
        f"{metadata['category_count']} categories, {len(featured)} featured"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
