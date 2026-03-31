---
name: book-forge
description: "Compile, synthesize, or author structured rule-based books for Candlekeep from source files, documentation folders, knowledge bases, or from scratch. Use this skill when the user wants to GENERATE new book content — transforming existing docs/KB/references into a Candlekeep book, writing a book about a topic for AI agents, or adding new chapters with new source material to an existing book. Trigger phrases: 'forge a book', 'compile into a book', 'turn my KB/docs into a book', 'create a Candlekeep book from', 'distill into a book', 'add a chapter about [topic]', 'book from my references'. IMPORTANT: Do NOT trigger for reading, searching, browsing, or managing existing Candlekeep library items — those go to the candlekeep skill. Do NOT trigger for editing book titles/metadata, listing library contents, marketplace browsing, or removing books. The distinguishing signal is whether the user wants to PRODUCE new structured content from sources or knowledge (book-forge) vs CONSUME or MANAGE existing library items (candlekeep)."
---

# Book Forge

Generate structured, rule-based books optimized for AI agent consumption via Candlekeep. The output format follows the patterns established by Candlekeep's published books (cybersecurity: 3,910 pages distilled to 238 rules across 32 chapters; UI/UX: 1,400 pages distilled to 170+ rules).

The core principle: agents need clear, unambiguous rules — not narrative prose. Every sentence is a directive, not a story.

## Three Modes

### 1. Compile Mode
Transform existing source files (KB folders, docs, markdown references) into a Candlekeep book.

**When to use:** User points to a folder of files or a set of documents.

### 2. Author Mode
Research a topic using model knowledge and write a book from scratch.

**When to use:** User names a topic but has no source files.

### 3. Append Mode
Add new content to an existing Candlekeep book — insert rules into existing chapters or create new chapters.

**When to use:** User wants to update a book that's already in their Candlekeep library.

### 4. Refresh Mode
Sync a book's node/version references against a live data source (e.g., n8n-buddy's node-versions cache). Finds stale typeVersions, deprecated parameter names, and outdated node type strings, then updates the affected rules.

**When to use:** User says "refresh", "sync versions", "update node versions", or the book contains technology-specific version references that may have drifted from the live system.

**Trigger phrase:** `book-forge refresh <candlekeep-id>`

**Refresh workflow:**
1. **Load version source:** Read `~/.claude/skills/n8n-buddy/cache/node-versions.json` (or another specified cache file)
2. **Download book:** `ck items get <id> --no-session > /tmp/book-refresh-<id>.md`
3. **Run diff script:** Execute `python3 ~/.claude/skills/book-forge/scripts/refresh-versions.py` which:
   - Parses every rule for typeVersion numbers, node type strings, and version-sensitive parameter names
   - Compares against the cache
   - Outputs a JSON report: `{stale_rules: [{rule_id, field, book_value, cache_value, context}], up_to_date: N, not_in_cache: N}`
4. **Present stale rules to user** for approval (some version changes may require rule content rewriting, not just number bumps)
5. **Update rules:** For simple version bumps, do mechanical find-replace. For rules where the parameter name or behavior changed, use a sonnet agent to rewrite the rule.
6. **Verify & publish:** Run integrity checks, publish new version.

**Important:** The refresh script is non-destructive — it reports what's stale but doesn't auto-modify without approval. The user always sees the diff before changes are applied.

## Workflow

The workflow has 6 phases. Phases 1-2 are interactive (require user approval). Phases 3-6 can run autonomously.

### Phase 1: Input Analysis

**Compile mode:**
1. Identify all source files. Fan out subagents in parallel to read and summarize each file (or batch of small files). Each subagent returns:
   - File path
   - Topic summary (2-3 sentences)
   - Key concepts/rules extractable from this file
   - Knowledge type: procedural, reference, conceptual, or troubleshooting

2. Merge summaries into a **topic map** — a grouped list of all concepts organized by theme.

**Author mode:**
1. Research the topic. Identify the major subtopics, key principles, common pitfalls, and best practices.
2. Build the topic map from research.

**Append mode:**
1. Download the existing book: `ck items get <id> --no-session > /tmp/book-<id>.md`
2. Parse its structure — extract chapter titles, scope declarations, and existing rules.
3. Read the new source material (same as compile mode).
4. Determine placement: which new content fits into existing chapters vs. needs new chapters.

### Phase 2: Outline & User Approval

Present the user with:
- **Book title and summary** (1 paragraph describing what the book covers and what it does NOT cover)
- **Chapter outline** — each chapter with:
  - Title (precise scope statement, not vague)
  - Scope declaration (what topics this chapter covers)
  - Estimated rule count
  - Source files mapped to this chapter (compile mode)

Wait for user approval before proceeding. The user may merge chapters, split them, reorder, or add/remove topics.

### Phase 3: Chapter Writing

Fan out subagents in parallel — one per chapter. This applies to ALL modes (compile, author, and append for new chapters). Each subagent receives:
- The chapter's scope declaration and title
- The relevant source material (compile mode) or topic description (author mode)
- The rule template format (read from `references/book-format.md`)
- Strict instructions to stay within scope — do not write about topics assigned to other chapters
- HARD LIMIT: Maximum 6 rules per chapter. If more rules are needed, split into multiple chapters with distinct scopes and cross-references linking them.

Each subagent produces a complete chapter in the standard format.

### Phase 4: Assembly & Dedup

Single agent merges all chapters into one document:
1. Assemble chapters in order
2. Scan for duplicate or near-duplicate rules across chapters — remove or merge
3. Verify each chapter is self-contained (an agent reading only Chapter 8 should not need context from Chapter 3)
4. Add the book summary/metadata section at the top

### Phase 5: Cross-References & TOC

After assembly, inject cross-references and build the final TOC:
1. For each chapter, scan all other chapters for related topics
2. Add a "Related" section at the end of each chapter with rich cross-references:
   `For webhook error handling patterns, see Chapter 7: Error Recovery (Rules 7.1-7.5)`
3. Build the table of contents with chapter titles and page/section indicators
4. The TOC should be detailed enough for an agent to pick the right chapter from the TOC alone

### Phase 6: Publish

Upload to Candlekeep:
- **New book:** `ck items create "Book Title"` then `ck items put <id> --file /tmp/book-forge-output.md --no-session`
- **Updated book (append):** `ck items put <id> --file /tmp/book-forge-output.md --no-session`

Report to the user: book title, chapter count, total rule count, and the Candlekeep item ID.

## Subagent Architecture

### Source Reader Agents (Phase 1, Compile mode)
- **Purpose:** Read and summarize source files in parallel
- **Model:** haiku (fast, cheap — just summarizing)
- **Input:** 1-5 source files per agent
- **Output:** Structured summary with topics, concepts, knowledge type

### Chapter Writer Agents (Phase 3)
- **Purpose:** Write one complete chapter following the rule template
- **Model:** sonnet (good balance of quality and speed)
- **Input:** Chapter scope, source material, rule template
- **Output:** Complete chapter markdown

### The orchestrator (main agent) handles:
- Phase 2 (user interaction)
- Phase 4 (dedup requires cross-chapter visibility)
- Phase 5 (cross-references require full book visibility)
- Phase 6 (publishing)

## Rule Format

Read `references/book-format.md` for the complete rule template and examples. The key elements of every rule:

1. **Rule number** (chapter.rule format: 3.1, 3.2, etc.)
2. **Rule title** — imperative, actionable statement
3. **Impact** — CRITICAL / HIGH / MEDIUM / LOW (opt-out: skip if the domain doesn't suit severity ratings)
4. **Description** — 1-3 sentences explaining the rule
5. **Good example** — correct implementation or approach
6. **Bad example** — what to avoid (with explanation of why it's wrong)
7. **Verification** — how to check compliance with this rule
8. **Common mistakes** — 1-3 pitfalls when applying this rule

## Chapter Structure

Every chapter follows this structure:

```markdown
# Chapter N: [Precise Title — Subtopics Listed]

> **Scope:** This chapter covers [X, Y, Z]. For [related topic A], see Chapter M.

## Rules

### Rule N.1: [Imperative Rule Title]
...rules in standard format...

### Rule N.2: [Imperative Rule Title]
...

## Related
- For [topic], see Chapter M: [Title] (Rules M.1-M.3)
- For [topic], see Chapter K: [Title] (Rules K.5-K.7)
```

## Book Metadata Header

Every book starts with this header (before the TOC):

```markdown
# [Book Title]

**Domain:** [e.g., n8n Workflow Automation, Web Security, UI/UX Design]
**Audience:** AI agents performing [specific task]
**Coverage:** This book covers [what's included]. It does NOT cover [explicit exclusions].
**Rule count:** [total] rules across [N] chapters
**Last updated:** [date]
```

## Important Principles

**Write for agents, not humans.** No narrative motivation, no anecdotes, no "imagine you're building..." framing. Every sentence is a directive or a fact. Agents need rules, not stories.

**Self-contained chapters.** An agent may read only one chapter. That chapter must make complete sense on its own. If a concept from another chapter is needed, provide a brief inline definition plus a cross-reference — don't assume the agent read the other chapter.

**Precise TOC entries.** Bad: "Chapter 5: Advanced Topics." Good: "Chapter 5: Error Handling — Retry Logic, Dead Letter Queues, Timeout Configuration, Circuit Breakers." The TOC is the agent's primary navigation tool.

**Page sizing: HARD LIMIT of 6 rules per chapter.** In Candlekeep, each `#` (level 1) heading creates a page boundary. Level 2+ headings (`##`, `###`) stay within their parent page. Each chapter uses one `#` heading, so each chapter = one page. **A chapter MUST NOT contain more than 6 rules. This is a non-negotiable constraint.** If a topic needs more than 6 rules, split it into two or more chapters with distinct scopes. Ensure all cross-references and related sections correctly link split chapters together. When splitting, each resulting chapter must be self-contained — an agent reading only one split chapter should understand the rules without needing the sibling chapter.

**Impact ratings reflect cost of ignoring the rule.** CRITICAL = system failure, data loss, security breach. HIGH = significant bugs or performance issues. MEDIUM = suboptimal but functional. LOW = style or convenience improvement.

**Cross-references are rich.** Bad: "See Chapter 5." Good: "For retry configuration patterns and dead letter queue setup, see Chapter 5: Error Recovery (Rules 5.1-5.5)." The agent should know whether to follow the reference without reading the TOC.
