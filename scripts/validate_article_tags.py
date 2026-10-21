import re
import sys
from collections import Counter
from pathlib import Path


BLOG_DIR = Path("content/blog")
SCOPED_PREFIXES = ("2023-", "2024-", "2025-", "2026-08-01-")
MIN_TAGS = 3
MAX_TAGS = 6

DISALLOWED_TAGS = {
    "AWS SSO": "IAM Identity Center",
    "AWS-SSO": "IAM Identity Center",
    "AgentCore": "Amazon Bedrock AgentCore",
    "Best Practices": "Use the specific practice",
    "cli": "CLI",
    "git": "Git",
    "Programming": "Use the language or engineering concept",
    "SFDX": "Salesforce CLI",
    "sfdx": "Salesforce CLI",
    "Technology": "Use the specific product or concept",
}


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}, text

    data = {}
    current = None
    for line in match.group(1).splitlines():
        item = re.match(r"^\s+-\s*(.+?)\s*$", line)
        if item and current:
            data.setdefault(current, []).append(item.group(1).strip().strip('"\''))
            continue
        pair = re.match(r"^([^:]+):\s*(.*)$", line)
        if pair:
            current = pair.group(1).strip()
            value = pair.group(2).strip().strip('"\'')
            data[current] = value if value else []
    return data, text


def scoped_paths():
    paths = []
    for path in BLOG_DIR.glob("*.md"):
        if not path.name.startswith(SCOPED_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        # Articles reviewed in the 2026-08-01 pass stay in scope after later
        # maintenance passes bump their reviewed_at (for example 2026-10-21).
        if path.name.startswith("2026-08-01-") or re.search(r"^reviewed_at: 2026-", text, re.M):
            paths.append(path)
    return sorted(paths)


def replacement_path(url):
    if not url.startswith("/blog/"):
        return BLOG_DIR / "__invalid_replacement__.en.md"
    name = url.rsplit("/", 1)[-1].removesuffix(".html")
    return BLOG_DIR / f"{name}.en.md"


def validate():
    errors = []
    records = {}
    frequencies = Counter()

    for path in scoped_paths():
        data, _ = frontmatter(path)
        tags = data.get("tags", [])
        records[path] = data
        if not isinstance(tags, list):
            errors.append(f"{path}: tags must use a multiline YAML list")
            continue
        if not MIN_TAGS <= len(tags) <= MAX_TAGS:
            errors.append(f"{path}: expected {MIN_TAGS}-{MAX_TAGS} tags, found {len(tags)}")
        folded = [tag.casefold() for tag in tags]
        if len(folded) != len(set(folded)):
            errors.append(f"{path}: duplicate tags after case normalization")
        for tag in tags:
            frequencies[tag] += 1
            if tag in DISALLOWED_TAGS:
                errors.append(f"{path}: replace tag '{tag}' with '{DISALLOWED_TAGS[tag]}'")
            if "," in tag:
                errors.append(f"{path}: split comma-combined tag '{tag}'")

    for path, data in records.items():
        if data.get("maintenance_status") != "archived":
            continue
        if "replacement_url_ko" in data:
            errors.append(f"{path}: replacement_url_ko is retired")
        original_tags = set(data.get("tags", []))
        for field in ("replacement_url_en",):
            target = replacement_path(data.get(field, ""))
            target_data = records.get(target)
            if not target_data:
                errors.append(f"{path}: cannot inspect {field} target {target}")
                continue
            shared = original_tags & set(target_data.get("tags", []))
            if len(shared) < 2:
                errors.append(f"{path}: {field} shares fewer than two tags ({sorted(shared)})")

    for path, data in records.items():
        if data.get("maintenance_status") == "archived":
            continue
        tags = data.get("tags", [])
        if isinstance(tags, list) and tags and not any(frequencies[tag] > 1 for tag in tags):
            errors.append(f"{path}: no tag connects this article to another reviewed article")

    return errors, frequencies


def main():
    errors, frequencies = validate()
    if errors:
        print(f"Tag validation FAILED with {len(errors)} error(s).")
        for error in errors:
            print(f"- {error}")
        return 1

    singletons = sum(1 for count in frequencies.values() if count == 1)
    print(
        "Tag validation PASSED: "
        f"{len(scoped_paths())} articles, {len(frequencies)} canonical tags, "
        f"{singletons} singleton tags."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
