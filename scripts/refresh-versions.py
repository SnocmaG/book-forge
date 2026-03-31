#!/usr/bin/env python3
"""
Book Forge — Refresh Mode: Version Sync Script

Compares a Candlekeep book's node version references against a live
version cache (e.g., n8n-buddy's node-versions.json).

Outputs a JSON report of stale rules that need updating.

Usage:
    python3 refresh-versions.py <book_file> [--cache <cache_file>]

Default cache: ~/.claude/skills/n8n-buddy/cache/node-versions.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_CACHE = Path.home() / ".claude/skills/n8n-buddy/cache/node-versions.json"

# ── Node type aliases: human-readable names → possible type strings ──
NODE_ALIASES = {
    "webhook": "n8n-nodes-base.webhook",
    "http request": "n8n-nodes-base.httpRequest",
    "http": "n8n-nodes-base.httpRequest",
    "gmail": "n8n-nodes-base.gmail",
    "google sheets": "n8n-nodes-base.googleSheets",
    "slack": "n8n-nodes-base.slack",
    "telegram": "n8n-nodes-base.telegram",
    "code": "n8n-nodes-base.code",
    "set": "n8n-nodes-base.set",
    "if": "n8n-nodes-base.if",
    "switch": "n8n-nodes-base.switch",
    "merge": "n8n-nodes-base.merge",
    "split in batches": "n8n-nodes-base.splitInBatches",
    "loop over items": "n8n-nodes-base.splitInBatches",
    "ai agent": "@n8n/n8n-nodes-langchain.agent",
    "agent": "@n8n/n8n-nodes-langchain.agent",
    "openai": "@n8n/n8n-nodes-langchain.openAi",
    "postgres": "n8n-nodes-base.postgres",
    "google drive": "n8n-nodes-base.googleDrive",
    "jira": "n8n-nodes-base.jira",
    "hubspot": "n8n-nodes-base.hubspot",
    "discord": "n8n-nodes-base.discord",
    "airtable": "n8n-nodes-base.airtable",
    "notion": "n8n-nodes-base.notion",
    "form trigger": "n8n-nodes-base.formTrigger",
    "chat trigger": "@n8n/n8n-nodes-langchain.chatTrigger",
    "schedule trigger": "n8n-nodes-base.scheduleTrigger",
    "execute workflow": "n8n-nodes-base.executeWorkflow",
    "google calendar": "n8n-nodes-base.googleCalendar",
}


def load_cache(cache_path):
    """Load the node version cache."""
    with open(cache_path) as f:
        data = json.load(f)
    return data.get("versions", {}), data.get("_meta", {})


def parse_book(book_text):
    """Parse book into rules with their chapter context."""
    rules = []
    # Match each rule block
    for match in re.finditer(
        r'^(### Rule (\d+\.\d+): .+?)(?=^### Rule \d+\.\d+:|^## Related|^# Chapter \d+:|\Z)',
        book_text,
        re.MULTILINE | re.DOTALL,
    ):
        rule_text = match.group(1)
        rule_id = match.group(2)

        # Find which chapter this rule belongs to
        ch_start = book_text.rfind("# Chapter ", 0, match.start())
        ch_match = re.match(r'# Chapter (\d+): (.+)', book_text[ch_start:ch_start + 200])
        ch_num = ch_match.group(1) if ch_match else "?"
        ch_title = ch_match.group(2).strip() if ch_match else "?"

        rules.append({
            "rule_id": rule_id,
            "chapter": ch_num,
            "chapter_title": ch_title,
            "text": rule_text,
            "start": match.start(),
            "end": match.end(),
        })

    return rules


def find_version_references(rule):
    """Find all typeVersion references in a rule."""
    refs = []
    text = rule["text"]

    # Pattern 1: "typeVersion: X.Y" or "typeVersion X.Y" in JSON/text
    for m in re.finditer(r'typeVersion["\s:]+(\d+(?:\.\d+)?)', text):
        refs.append({
            "type": "typeVersion_json",
            "value": float(m.group(1)),
            "context": text[max(0, m.start() - 50):m.end() + 50].strip(),
            "match": m.group(0),
        })

    # Pattern 2: "typeVersion 2.1" in prose
    for m in re.finditer(r'typeVersion\s+(\d+(?:\.\d+)?)', text):
        refs.append({
            "type": "typeVersion_prose",
            "value": float(m.group(1)),
            "context": text[max(0, m.start() - 50):m.end() + 50].strip(),
            "match": m.group(0),
        })

    # Pattern 3: "version X.Y" near a node type string
    for m in re.finditer(r'(?:version|v)(?:\s+|: ?)(\d+(?:\.\d+)?)', text, re.IGNORECASE):
        refs.append({
            "type": "version_mention",
            "value": float(m.group(1)),
            "context": text[max(0, m.start() - 80):m.end() + 80].strip(),
            "match": m.group(0),
        })

    # Pattern 4: Full node type strings in the text
    for m in re.finditer(r'(?:n8n-nodes-base|@n8n/n8n-nodes-langchain)\.(\w+)', text):
        full_type = m.group(0)
        refs.append({
            "type": "node_type_string",
            "value": full_type,
            "context": text[max(0, m.start() - 30):m.end() + 30].strip(),
            "match": full_type,
        })

    return refs


def identify_node_type(rule, refs):
    """Try to identify which n8n node a rule is about."""
    text = rule["text"].lower()
    title = rule["chapter_title"].lower()

    # Check for explicit node type strings
    for ref in refs:
        if ref["type"] == "node_type_string":
            return ref["value"]

    # Check aliases against rule text and chapter title
    combined = text + " " + title
    for alias, node_type in NODE_ALIASES.items():
        if alias in combined:
            return node_type

    return None


def is_in_dont_section(rule_text, match_pos):
    """Check if a version reference is inside a **Don't:** example (intentionally old)."""
    # Look backwards from the match position for **Do:** or **Don't:** markers
    text_before = rule_text[:match_pos]
    last_do = text_before.rfind("**Do:**")
    last_dont = text_before.rfind("**Don't:**")
    last_wrong = text_before.rfind("*Why wrong:")

    # If the closest preceding marker is Don't or Why wrong, this is an intentional bad example
    markers = [
        ("do", last_do),
        ("dont", last_dont),
        ("wrong", last_wrong),
    ]
    markers = [(label, pos) for label, pos in markers if pos >= 0]
    if not markers:
        return False

    closest = max(markers, key=lambda x: x[1])
    return closest[0] in ("dont", "wrong")


def compare(rules, cache):
    """Compare rule version references against cache."""
    stale = []
    intentional_old = 0
    up_to_date = 0
    not_in_cache = 0
    no_version_refs = 0

    for rule in rules:
        refs = find_version_references(rule)

        if not refs:
            no_version_refs += 1
            continue

        node_type = identify_node_type(rule, refs)

        if not node_type or node_type not in cache:
            not_in_cache += 1
            continue

        cache_version = cache[node_type]

        for ref in refs:
            if ref["type"] in ("typeVersion_json", "typeVersion_prose"):
                if ref["value"] < cache_version:
                    # Check if this is inside a Don't/Why wrong section (intentionally old)
                    match_pos = rule["text"].find(ref["match"])
                    if is_in_dont_section(rule["text"], match_pos):
                        intentional_old += 1
                        continue

                    stale.append({
                        "rule_id": rule["rule_id"],
                        "chapter": rule["chapter"],
                        "chapter_title": rule["chapter_title"],
                        "node_type": node_type,
                        "field": "typeVersion",
                        "book_value": ref["value"],
                        "cache_value": cache_version,
                        "context": ref["context"],
                        "match": ref["match"],
                    })
                else:
                    up_to_date += 1

    return {
        "stale_rules": stale,
        "up_to_date": up_to_date,
        "intentional_old": intentional_old,
        "not_in_cache": not_in_cache,
        "no_version_refs": no_version_refs,
        "total_rules": len(rules),
    }


def main():
    parser = argparse.ArgumentParser(description="Book Forge — Refresh Mode version scanner")
    parser.add_argument("book_file", help="Path to the Candlekeep book markdown file")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="Path to node-versions.json cache")
    parser.add_argument("--output", default="/tmp/book-refresh-report.json", help="Output report path")
    args = parser.parse_args()

    # Load inputs
    print(f"Loading cache from: {args.cache}")
    cache, meta = load_cache(args.cache)
    print(f"  Cache synced: {meta.get('synced_at', 'unknown')}")
    print(f"  Source: {meta.get('source', 'unknown')}")
    print(f"  Node types: {len(cache)}")

    print(f"\nParsing book: {args.book_file}")
    with open(args.book_file) as f:
        book_text = f.read()
    rules = parse_book(book_text)
    print(f"  Rules parsed: {len(rules)}")

    # Compare
    print("\nComparing versions...")
    report = compare(rules, cache)
    report["cache_meta"] = meta

    # Output
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print(f"\n{'=' * 50}")
    print(f"REFRESH REPORT")
    print(f"{'=' * 50}")
    print(f"Total rules scanned:     {report['total_rules']}")
    print(f"Rules with version refs: {report['total_rules'] - report['no_version_refs']}")
    print(f"Up to date:              {report['up_to_date']}")
    print(f"Intentional old (Don't): {report.get('intentional_old', 0)}")
    print(f"STALE (need update):     {len(report['stale_rules'])}")
    print(f"Not in cache:            {report['not_in_cache']}")

    if report["stale_rules"]:
        print(f"\n{'─' * 50}")
        print("STALE RULES:")
        print(f"{'─' * 50}")
        for item in report["stale_rules"]:
            print(f"\n  Rule {item['rule_id']} (Ch {item['chapter']}: {item['chapter_title']})")
            print(f"  Node: {item['node_type']}")
            print(f"  Book says: {item['field']} = {item['book_value']}")
            print(f"  Cache says: {item['field']} = {item['cache_value']}")
            print(f"  Context: ...{item['context']}...")

    print(f"\nReport saved to: {args.output}")
    return 1 if report["stale_rules"] else 0


if __name__ == "__main__":
    sys.exit(main())
