#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

MIN_SKILLS = 1000
SOURCE = {
    "key": "voltagent-awesome-agent-skills",
    "name": "VoltAgent Awesome Agent Skills",
    "repository": "VoltAgent/awesome-agent-skills",
    "page": "https://github.com/VoltAgent/awesome-agent-skills",
    "index_url": "https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/main/README.md",
    "license_url": "https://raw.githubusercontent.com/VoltAgent/awesome-agent-skills/main/LICENSE",
    "commit_api": "https://api.github.com/repos/VoltAgent/awesome-agent-skills/commits/main",
    "repo_api": "https://api.github.com/repos/VoltAgent/awesome-agent-skills",
}

SUMMARY_RE = re.compile(r"<summary>\s*<h[1-6][^>]*>(.*?)</h[1-6]>\s*</summary>", re.I)
HEADING_RE = re.compile(r"^\s*#{2,4}\s+(.+?)\s*$")
BOLD_ITEM_RE = re.compile(
    r"^\s*[-*]\s+\*\*\[([^\]]+)\]\((https?://[^)]+)\)\*\*"
    r"\s*(?:(?:-|–|—|:)\s*)?(.*?)\s*$"
)
PLAIN_ITEM_RE = re.compile(
    r"^\s*[-*]\s+\[([^\]]+)\]\((https?://[^)]+)\)"
    r"\s*(?:(?:-|–|—|:)\s*)?(.*?)\s*$"
)
LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
SLUG_RE = re.compile(r"[^a-z0-9]+")

ALLOWED_HOSTS = {
    "github.com", "www.github.com", "officialskills.sh", "www.officialskills.sh",
    "skills.sh", "www.skills.sh", "agentskills.io", "www.agentskills.io",
    "agentskills.in", "www.agentskills.in", "npmjs.com", "www.npmjs.com",
    "pypi.org", "marketplace.visualstudio.com",
}
REJECT_NAMES = {
    "sponsor", "discord", "twitter", "everyfeed", "launchkit",
    "table of contents", "quality standards",
}
REJECT_URLS = {
    "sponsors.", "/sponsor", "discord.gg", "discord.com", "twitter.com",
    "x.com/", "everyfeed.ai", "launchkit.",
}
FIELDS = [
    "id", "name", "publisher", "category", "description", "url",
    "origin_repository", "source_type", "record_type", "install_status",
    "verification_status", "listing_source", "source_commit", "indexed_at",
]


def plain_text(value: str) -> str:
    value = html.unescape(value or "")
    value = LINK_RE.sub(r"\1", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = TAG_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip(" -–—:|")


def slugify(value: str) -> str:
    return SLUG_RE.sub("-", plain_text(value).lower()).strip("-") or "uncategorized"


def canonical_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/")
    query = urllib.parse.urlencode([
        (key, val)
        for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source"}
    ])
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, query, ""))


def origin_repository(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    if parsed.netloc.lower() in {"github.com", "www.github.com"} and len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    if parsed.netloc.lower() in {"officialskills.sh", "www.officialskills.sh"} and parts:
        return f"{parts[0]}/skills"
    return ""


def infer_publisher(name: str, url: str, category: str) -> str:
    if "/" in name:
        return name.split("/", 1)[0].strip()
    repo = origin_repository(url)
    if "/" in repo:
        return repo.split("/", 1)[0]
    cleaned = re.sub(
        r"^(official\s+|skills?\s+by\s+|skill\s+by\s+)",
        "", plain_text(category), flags=re.I,
    ).strip()
    return cleaned or urllib.parse.urlsplit(url).netloc


def source_type(category: str) -> str:
    lower = category.lower()
    if "community" in lower:
        return "community"
    if "official" in lower or lower.startswith("skills by") or lower.startswith("skill by"):
        return "maintainer-published"
    return "curated"


def looks_like_skill(name: str, url: str, category: str, *, bold: bool) -> bool:
    name_l = plain_text(name).lower()
    url_l = url.lower()
    if not name_l or not category:
        return False
    if any(fragment in name_l for fragment in REJECT_NAMES):
        return False
    if any(fragment in url_l for fragment in REJECT_URLS):
        return False
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if not bold and "skill" not in category.lower():
        return False
    if parsed.netloc.lower() not in ALLOWED_HOSTS and "/" not in name:
        return False
    return True


def parse_skill_index(markdown: str, *, source_key: str) -> list[dict[str, str]]:
    category = "Uncategorized Skills"
    by_url: dict[str, dict[str, str]] = {}
    for raw in markdown.splitlines():
        line = raw.rstrip()
        summary = SUMMARY_RE.search(line)
        if summary:
            category = plain_text(summary.group(1)) or category
            continue
        heading = HEADING_RE.match(line)
        if heading:
            candidate = plain_text(heading.group(1))
            if "skill" in candidate.lower() and "table of contents" not in candidate.lower():
                category = candidate
            continue
        match = BOLD_ITEM_RE.match(line)
        bold = True
        if not match:
            match = PLAIN_ITEM_RE.match(line)
            bold = False
        if not match:
            continue
        name, url, description = match.groups()
        name = plain_text(name)
        url = canonical_url(url)
        if not looks_like_skill(name, url, category, bold=bold):
            continue
        description = plain_text(description) or (
            "Upstream index did not provide a description; inspect the linked source before use."
        )
        by_url.setdefault(url, {
            "id": "skill-" + hashlib.sha1(url.encode()).hexdigest()[:12],
            "name": name,
            "publisher": infer_publisher(name, url, category),
            "category": plain_text(category),
            "description": description,
            "url": url,
            "origin_repository": origin_repository(url),
            "source_type": source_type(category),
            "record_type": "real-skill-index-entry",
            "install_status": "not-installed",
            "verification_status": "indexed-link-not-audited",
            "listing_source": source_key,
            "source_commit": "",
            "indexed_at": "",
        })
    return sorted(
        by_url.values(),
        key=lambda row: (
            row["category"].casefold(), row["publisher"].casefold(),
            row["name"].casefold(), row["url"],
        ),
    )


def fetch_bytes(url: str, retries: int = 4) -> bytes:
    error: Exception | None = None
    headers = {
        "User-Agent": "RoadOfFlower-Skill-Indexer/1.0",
        "Accept": "application/vnd.github+json, text/plain;q=0.9, */*;q=0.8",
    }
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to fetch {url}: {error}")


def fetch_text(url: str) -> str:
    return fetch_bytes(url).decode("utf-8")


def fetch_source() -> tuple[str, dict[str, str], str]:
    markdown = fetch_text(SOURCE["index_url"])
    license_text = fetch_text(SOURCE["license_url"])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    commit_sha, commit_date, license_name = "unknown", now, "MIT"
    try:
        commit = json.loads(fetch_text(SOURCE["commit_api"]))
        commit_sha = str(commit.get("sha") or "unknown")
        commit_date = str(commit.get("commit", {}).get("committer", {}).get("date") or now)
    except Exception as exc:
        print(f"warning: source commit metadata unavailable: {exc}", file=sys.stderr)
    try:
        repo = json.loads(fetch_text(SOURCE["repo_api"]))
        license_name = str((repo.get("license") or {}).get("spdx_id") or "MIT")
    except Exception as exc:
        print(f"warning: repository metadata unavailable: {exc}", file=sys.stderr)
    return markdown, {
        "source_key": SOURCE["key"], "source_name": SOURCE["name"],
        "source_repository": SOURCE["repository"], "source_page": SOURCE["page"],
        "source_index_url": SOURCE["index_url"], "source_commit": commit_sha,
        "source_commit_date": commit_date, "source_license": license_name,
    }, license_text


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")


def readme(records: list[dict[str, str]], meta: dict[str, str]) -> str:
    count = len(records)
    categories = len({row["category"] for row in records})
    publishers = len({row["publisher"] for row in records})
    return f"""# RoadOfFlower · Agent Skill 花路

> 让真正可用的 Agent Skill 更容易被发现、理解、组合与验证，让新人少走信息差造成的弯路。

RoadOfFlower 是一个**真实 Agent Skill 索引与学习项目**。这里不再用批量生成的名称冒充可用 Skill，也不要求你先安装任何东西：我们维护可点击、可追溯的外部 Skill 链接，并配套 Agent 入门、选型、工作流组合、定制、结果验证与风险控制教程。

## 当前规模

- **{count:,} 条真实 Skill 索引记录**，每条均指向现有外部页面或代码仓库。
- **{categories} 个上游分类**，**{publishers} 个发布者或来源组织**。
- 来源：[{meta['source_name']}]({meta['source_page']})，固定到提交 `{meta['source_commit'][:12]}`。
- 本仓库没有安装或审计这些 Skill；统一状态为 `not-installed / indexed-link-not-audited`。

## 快速入口

| 目标 | 入口 |
|---|---|
| 浏览完整索引 | [skills/INDEX.md](skills/INDEX.md) |
| 下载数据 | [CSV](skills/catalog.csv) · [JSON](skills/catalog.json) |
| 关键词搜索 | `python scripts/search_skills.py "pdf" --limit 10` |
| Agent 入门 | [docs/01-agent-basics.md](docs/01-agent-basics.md) |
| 选择 Skill | [docs/02-find-and-evaluate-skills.md](docs/02-find-and-evaluate-skills.md) |
| 组合工作流 | [docs/03-compose-workflows.md](docs/03-compose-workflows.md) |
| 定制 Agent/Skill | [docs/04-customize-agent-and-skill.md](docs/04-customize-agent-and-skill.md) |
| 验证与风险 | [docs/05-verify-results-and-control-risk.md](docs/05-verify-results-and-control-risk.md) |

## 项目如何工作

```mermaid
flowchart LR
    A[真实上游 Skill 索引] --> B[解析、规范化、去重]
    B --> C[CSV / JSON]
    B --> D[Markdown 与分类页]
    C --> E[本地搜索]
    D --> F[学习与选型]
    E --> G[组合、验证、实践]
    F --> G
```

## 三层内容

1. **发现层**：`skills/` 提供真实链接、发布者、分类、简介、原始仓库和来源提交。
2. **教学层**：`docs/` 从 Agent 基础讲到工具、工作流、定制、评测与风险控制。
3. **维护层**：同步脚本固定上游提交，验证器检查数量、唯一性、链接格式和真实性边界。

## 重要边界

- 被收录不等于安全、兼容、活跃或适合你的环境。
- 使用前必须阅读目标仓库的 Skill 文件、依赖、权限与许可证。
- 涉及删除、支付、发送、发布、账户权限、生产环境或隐私数据时，必须人工确认。
- RoadOfFlower 只做发现索引；外部 Skill 仍归各自作者所有。

## 为什么叫 RoadOfFlower

真正的“花路”不是一句祝福，而是一条不断维护的基础设施：有人补一条可靠链接，有人纠正一段错误简介，有人标出一个危险权限，有人把实践写成教程。每次维护都让后来者更接近自己的理想，而不是重复踩坑。

也祝愿 LED 在商业世界里成长为真正有分量的计算机技术大牛：技术判断扎实，商业选择清醒，产品被用户信任，团队愿意长期并肩，并且在成功之外保有健康、自由与内心踏实。🌸

## 贡献与许可证

贡献规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。本仓库原创代码和文档采用 [MIT License](LICENSE)；第三方来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
"""


def category_slugs(categories: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    used: set[str] = set()
    for category in sorted(set(categories), key=str.casefold):
        base = slugify(category)
        slug = base
        if slug in used:
            slug += "-" + hashlib.sha1(category.encode()).hexdigest()[:6]
        used.add(slug)
        result[category] = slug
    return result


def render_repository(root: Path, records: list[dict[str, str]], meta: dict[str, str], license_text: str) -> None:
    if not records:
        raise ValueError("cannot render an empty catalog")
    for row in records:
        row["source_commit"] = meta["source_commit"]
        row["indexed_at"] = meta["source_commit_date"]

    skills = root / "skills"
    if skills.exists():
        shutil.rmtree(skills)
    old_readme = root / "ReadMe.md"
    if old_readme.exists():
        old_readme.unlink()
    (skills / "categories").mkdir(parents=True)
    (root / "third_party").mkdir(parents=True, exist_ok=True)

    with (skills / "catalog.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(records)

    categories = Counter(row["category"] for row in records)
    publishers = Counter(row["publisher"] for row in records)
    metadata = {
        "record_type": "real-skill-index-entry", "record_count": len(records),
        "category_count": len(categories), "publisher_count": len(publishers),
        **meta, "install_status": "not-installed",
        "verification_status": "indexed-link-not-audited",
    }
    write(skills / "catalog.json", json.dumps({"metadata": metadata, "records": records}, ensure_ascii=False, indent=2))
    write(skills / "catalog_metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))
    write(skills / "sources.json", json.dumps({"sources": [meta]}, ensure_ascii=False, indent=2))
    write(root / "README.md", readme(records, meta))

    slugs = category_slugs(list(categories))
    category_rows = "\n".join(
        f"| [{category}](categories/{slugs[category]}.md) | {count} |"
        for category, count in categories.most_common()
    )
    publisher_rows = "\n".join(
        f"| {publisher.replace('|', '\\|')} | {count} |"
        for publisher, count in publishers.most_common(30)
    )
    write(skills / "README.md", f"""# 真实 Agent Skill 索引

这里收录外部真实 Skill 链接，不是自动生成的能力愿望，也不是已安装插件清单。

- 记录：**{len(records):,}**
- 来源：[{meta['source_name']}]({meta['source_page']})
- 提交：`{meta['source_commit']}`
- 状态：`not-installed / indexed-link-not-audited`

入口：[完整索引](INDEX.md) · [CSV](catalog.csv) · [JSON](catalog.json)

## 分类

| 分类 | 数量 |
|---|---:|
{category_rows}

## 发布者 Top 30

| 发布者 | 数量 |
|---|---:|
{publisher_rows}
""")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in records:
        grouped[row["category"]].append(row)
    index_lines = [
        "# RoadOfFlower Real Agent Skill Index", "",
        f"> {len(records):,} real links from [{meta['source_name']}]({meta['source_page']}) at `{meta['source_commit'][:12]}`.", "",
        "> Indexed only: not installed and not audited by RoadOfFlower.", "",
    ]
    for category in sorted(grouped, key=str.casefold):
        index_lines += [f"## {category} ({len(grouped[category])})", ""]
        page = [f"# {category}", "", f"> {len(grouped[category])} real external Skill links.", ""]
        for row in grouped[category]:
            repo = f" · `{row['origin_repository']}`" if row["origin_repository"] else ""
            item = f"- **[{row['name']}]({row['url']})** — {row['description']} _({row['publisher']}{repo})_"
            index_lines.append(item); page.append(item)
        index_lines.append(""); page += ["", "> Indexed only; not installed or audited."]
        write(skills / "categories" / f"{slugs[category]}.md", "\n".join(page))
    write(skills / "INDEX.md", "\n".join(index_lines))

    preferred = {"anthropics", "openai", "google", "vercel", "cloudflare", "stripe", "microsoft", "huggingface", "figma", "expo", "netlify", "supabase", "firebase", "mongodb", "redis", "nvidia", "datadog", "sentry"}
    featured = [row for row in records if slugify(row["publisher"]).replace("-", "") in {p.replace("-", "") for p in preferred}][:120]
    lines = ["# Featured Maintainer-Published Skills", "", "精选只是新人入口，不是安全审计名单。", ""]
    for row in featured:
        lines.append(f"- [{row['name']}]({row['url']}) — {row['description']}")
    write(skills / "FEATURED.md", "\n".join(lines))

    write(root / "THIRD_PARTY_NOTICES.md", f"""# Third-Party Notices

## {meta['source_name']}

- Repository: {meta['source_page']}
- Indexed commit: `{meta['source_commit']}`
- Reported license: `{meta['source_license']}`
- Use: names, URLs, categories and short descriptions are transformed into a discovery index containing {len(records):,} unique records.

The upstream project is not affiliated with RoadOfFlower. External Skill code is not copied here. Each linked project may have its own license and terms.

A captured copy of the upstream index license is stored at `third_party/VoltAgent-awesome-agent-skills-LICENSE`.
""")
    write(root / "third_party/VoltAgent-awesome-agent-skills-LICENSE", license_text)


def run(root: Path) -> int:
    markdown, meta, license_text = fetch_source()
    records = parse_skill_index(markdown, source_key=meta["source_key"])
    if len(records) < MIN_SKILLS:
        raise RuntimeError(f"parsed {len(records)} links; minimum is {MIN_SKILLS}")
    render_repository(root, records, meta, license_text)
    print(f"generated {len(records)} real Skill links at {meta['source_commit'][:12]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args(argv)
    return run(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
