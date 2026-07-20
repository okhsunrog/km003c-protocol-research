#!/usr/bin/env python3
"""Check that repository-local Markdown link targets exist."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]*]\(([^)\s]+)(?:\s+['\"][^'\"]*['\"])?\)")
EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "data:")


def markdown_files() -> list[Path]:
    return [
        PROJECT_ROOT / "README.md",
        PROJECT_ROOT / "tests" / "README.md",
        *sorted((PROJECT_ROOT / "docs").rglob("*.md")),
    ]


def broken_local_links(path: Path) -> list[tuple[str, int]]:
    """Return missing local targets and their source line numbers."""
    failures = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        for match in MARKDOWN_LINK.finditer(line):
            raw_target = match.group(1)
            if raw_target.startswith(EXTERNAL_SCHEMES) or raw_target.startswith("#"):
                continue

            target_text = unquote(raw_target.split("#", maxsplit=1)[0])
            if not target_text:
                continue
            target = (path.parent / target_text).resolve()
            if not target.exists():
                failures.append((raw_target, line_number))
    return failures


def main() -> int:
    failures = [
        (path, target, line_number)
        for path in markdown_files()
        for target, line_number in broken_local_links(path)
    ]
    for path, target, line_number in failures:
        relative_path = path.relative_to(PROJECT_ROOT)
        print(f"{relative_path}:{line_number}: missing local link target: {target}")
    if failures:
        print(f"Found {len(failures)} broken local Markdown link(s)")
        return 1

    print(f"Checked local links in {len(markdown_files())} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
