# Actual Agent Skill Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish at least 1,000 real Agent Skill links with traceable source metadata and a README that explains the project.

**Architecture:** A standard-library Python sync script parses a maintained upstream skill index and deterministically renders catalog artifacts. GitHub Actions runs parser tests, synchronizes, validates, and commits ordinary files without touching workflow files.

**Tech Stack:** Python 3.12 standard library, Markdown, CSV, JSON, GitHub Actions.

## Global Constraints

- Do not install external skills.
- Do not label an indexed link as audited, safe, or verified.
- Minimum unique entries: 1,000.
- Preserve third-party attribution and license notice.
- Generated commits must not modify `.github/workflows/`.

---

### Task 1: Parser contract

- [x] Write parser tests for heading tracking, real link extraction, duplicate removal, publisher/repository inference, and advertisement rejection.
- [x] Run tests and confirm failure before implementation.
- [x] Implement the parser and confirm all parser tests pass.

### Task 2: Deterministic renderer

- [x] Define CSV, JSON, Markdown, category, README and third-party notice outputs.
- [x] Add a renderer test for required files.
- [x] Keep generated output separate from static tutorials and tooling.

### Task 3: Safe GitHub Actions synchronization

- [x] Restrict push triggers to the sync script.
- [x] Guard against staged workflow-file changes.
- [x] Run synchronization against the live upstream index.
- [x] Confirm the generated commit pushes successfully.

### Task 4: PR and remote verification

- [x] Verify workflow conclusion is success.
- [x] Verify the branch contains the actual catalog artifacts.
- [x] Verify metadata count is at least 1,000.
- [x] Verify PR #1 tracks the generated branch head.
- [x] Record exact counts and validation evidence in `RELEASE_REPORT.md`.
- [x] Record that upstream PR metadata writes are blocked by the connected integration's HTTP 403 permission boundary.
