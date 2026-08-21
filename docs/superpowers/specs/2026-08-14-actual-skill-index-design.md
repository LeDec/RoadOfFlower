# Actual Agent Skill Index Design

## Goal

Turn RoadOfFlower from a generated task-blueprint catalog into a real, clickable, traceable Agent Skill discovery index with at least 1,000 entries, while retaining beginner education, customization guidance, verification, and risk-control material.

## Approved scope

- Index actual external Agent Skills; do not install or vendor their code.
- Every row includes a name, direct URL, publisher, category, short description, source index, and explicit `not-installed / not-audited` status.
- Use the MIT-licensed `VoltAgent/awesome-agent-skills` index as the initial upstream source, retain attribution, record the upstream commit, and preserve its license notice.
- Generate machine-readable CSV/JSON plus a human-readable Markdown index and category pages.
- Rewrite the repository README in Chinese to explain the project, quick-start search, learning path, truth boundary, contribution process, and the Road of Flowers theme.
- Keep synchronization reproducible through a Python standard-library script and GitHub Actions.
- The sync job may modify ordinary files only; it must never create, update, or delete workflow files.

## Architecture

1. `.bootstrap/sync_actual_skills.py` downloads and parses the upstream Markdown index.
2. Parser tests run before network synchronization.
3. The generator writes catalog data, category pages, README and third-party notices.
4. Static search, validation, tests and tutorials are versioned in the repository.
5. GitHub Actions validates the generated tree and commits it back to the existing feature branch.

## Failure handling

- Network retries use bounded exponential backoff.
- A sync fails if fewer than 1,000 unique real entries are parsed.
- Duplicate IDs and URLs, non-HTTP URLs, missing descriptions, or missing truth-boundary fields fail validation.
- Upstream failure leaves the last committed catalog intact.
