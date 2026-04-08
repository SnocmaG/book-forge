# Book Forge

A Claude Code skill for generating structured, rule-based reference books optimized for AI agent consumption via [Candlekeep](https://candlekeep.ai).

## What It Does

Book Forge transforms source material — documentation folders, knowledge bases, markdown references, or raw topic knowledge — into structured books that AI agents can efficiently consume. The output follows Candlekeep's proven format (e.g., their cybersecurity book distills 3,910 pages into 238 rules across 32 chapters).

**Core principle:** Agents need clear, unambiguous rules — not narrative prose. Every sentence is a directive, not a story.

## Modes

| Mode | Description | Trigger |
|------|-------------|---------|
| **Compile** | Transform existing source files (KB folders, docs, markdown) into a book | User points to a folder or set of documents |
| **Author** | Research a topic and write a book from scratch using model knowledge | User names a topic but has no source files |
| **Append** | Add new chapters or rules to an existing Candlekeep book | User wants to update an existing book with new content |
| **Refresh** | Sync version references against a live data source (e.g., n8n node versions) | User says "refresh" or "sync versions" |

## Workflow

The skill runs through 8 phases:

1. **Input Analysis** -- Read and summarize source material via parallel subagents (haiku for speed). Checks library and marketplace for existing books on the same topic -- flags overlapping or contradicting rules. Produces a topic map of all extractable concepts grouped by theme.
2. **Outline & Approval** -- Present chapter outline with scope declarations, estimated rule counts, and source mappings. Wait for user sign-off before writing.
3. **Chapter Writing** -- Fan out parallel subagents (sonnet), one per chapter. Each writes a complete, self-contained chapter following the rule template. Hard limit: 6 rules per chapter.
3.5. **Quality Gate** -- Validate every chapter for template compliance, rule count, scope adherence, self-containment, and no narrative prose. Chapters that fail get sent back for rewrite.
4. **Assembly & Dedup** -- Merge chapters, remove duplicate rules across chapters, verify each chapter stands alone.
5. **Cross-References & TOC** -- Inject rich cross-references between chapters. Build a detailed TOC that lets an agent pick the right chapter without reading the full book.
5.5. **Smoke Test** -- Pick 2-3 random chapters, generate a realistic sample problem for each, have a haiku agent attempt to solve it using only that chapter's rules. Reports problem, application, and result.
6. **Publish** -- Upload to Candlekeep via `ck` CLI. Post-publish validation via `ck items toc` confirms page boundaries and TOC integrity.

## Rule Format

Every rule follows a consistent structure:

```markdown
### Rule N.M: [Imperative Action Statement]
**Impact:** CRITICAL | HIGH | MEDIUM | LOW

[1-3 sentence description.]

**Do:**
[Correct example with annotation]

**Don't:**
[Incorrect example]
*Why wrong: [Failure mode explanation]*

**Verify:** [How to check compliance]

**Common mistakes:**
- [Pitfall 1]
- [Pitfall 2]
```

Impact ratings reflect cost of ignoring the rule:
- **CRITICAL** — System failure, data loss, security breach
- **HIGH** — Significant bugs or performance issues
- **MEDIUM** — Suboptimal but functional
- **LOW** — Style or convenience improvement

## Chapter Structure

```markdown
# Chapter N: [Precise Title — Subtopics Listed]

> **Scope:** This chapter covers [X, Y, Z]. For [related topic A], see Chapter M.

### Rule N.1: ...
### Rule N.2: ...
(max 6 rules)

## Related
- For [topic], see Chapter M: [Title] (Rules M.1-M.3)
```

Key constraints:
- **Max 6 rules per chapter** — if more are needed, split into multiple chapters with distinct scopes
- **Self-contained chapters** — an agent reading only one chapter gets full context
- **Precise TOC entries** — list specific subtopics, not vague categories
- **Rich cross-references** — include topic description + chapter + rule numbers

## Refresh Mode

The refresh mode keeps technology-specific version references up to date. It uses `scripts/refresh-versions.py` to:

1. Parse every rule for typeVersion numbers and node type strings
2. Compare against a live version cache (default: n8n-buddy's `node-versions.json`)
3. Output a JSON report of stale rules
4. Present findings for user approval before any changes are applied

The script is non-destructive — it reports what's stale but never auto-modifies.

```bash
python3 scripts/refresh-versions.py /tmp/book.md --cache path/to/versions.json
```

## Project Structure

```
book-forge/
├── SKILL.md                        # Main skill definition (Claude Code reads this)
├── references/
│   └── book-format.md              # Rule template and format reference
└── scripts/
    └── refresh-versions.py         # Version sync scanner for refresh mode
```

## Subagent Architecture

| Agent | Phase | Model | Purpose |
|-------|-------|-------|---------|
| Source Reader | 1 (Compile) | haiku | Read and summarize source files in parallel |
| Chapter Writer | 3 | sonnet | Write one complete chapter per agent |
| Quality Gate | 3.5 | haiku | Validate template compliance per chapter |
| Smoke Test | 5.5 | haiku | Test chapters against realistic sample problems |
| Orchestrator | 1-2, 4-6 | main | Overlap check, user interaction, dedup, cross-refs, publishing |

## Installation

This is a Claude Code skill. Place it in your skills directory:

```
~/.claude/skills/book-forge/
```

Claude Code will automatically detect and use it when triggered by phrases like:
- "forge a book from my docs"
- "compile this KB into a Candlekeep book"
- "add a chapter about [topic] to book [ID]"
- "refresh versions on book [ID]"

## Requirements

- [Candlekeep CLI](https://candlekeep.ai) (`ck`) installed and authenticated
- Claude Code with agent/subagent support
- Python 3.8+ (for refresh mode script)
