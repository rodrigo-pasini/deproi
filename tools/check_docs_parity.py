#!/usr/bin/env python3
"""Check that every English doc has a Brazilian Portuguese twin with the same structure.

Deproi documentation is written in English first, always with a pt-BR equivalent
next to it: ``README.md`` + ``README.pt-BR.md``, ``docs/x.md`` + ``docs/x.pt-BR.md``.
English is the source of truth; a change to it updates the pt-BR file in the same PR.

Rules, per pair:
  1. both files exist (an English doc without a twin, or an orphan twin, fails);
  2. the first non-empty line is the language switcher and links to the twin;
  3. same sequence of heading levels (headings inside code fences are ignored);
  4. same sequence of code fences, by info string (``bash``, ``json``…);
  5. same number of images;
  6. every relative link and image resolves to an existing file, in both languages.

Usage: ``python tools/check_docs_parity.py [ROOT]`` — exit 0 when clean, 1 otherwise.
Standard library only.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PT_SUFFIX = ".pt-BR.md"

# Files that are deliberately single-language.
EXEMPT_FILES = {
    "CLAUDE.md",  # a one-line pointer to AGENTS.md, read by tools, not people
    "PLANO.md",  # internal planning notes (pt-BR only), removed before v1.0
}
# .github holds GitHub-specific files (templates) that GitHub reads from a single path: bilingual inline.
# skills/ holds agent skill files, read by tools in one language.
EXEMPT_DIRS = {".git", ".github", "skills", ".venv", "venv", "node_modules", ".pytest_cache", ".ruff_cache", "fixtures"}

_HEADING = re.compile(r"^(#{1,6})\s+\S")
_FENCE = re.compile(r"^\s*(```+|~~~+)\s*([\w+-]*)")
# [text](target) and ![alt](target); the target stops at whitespace or ")".
_LINK = re.compile(r"(!?)\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_HTML_IMG = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_HTML_HREF = re.compile(r"<a\b[^>]*\bhref=[\"']([^\"']+)[\"']", re.IGNORECASE)


@dataclass
class Structure:
    switcher: str = ""
    headings: list[int] = field(default_factory=list)
    fences: list[str] = field(default_factory=list)
    images: int = 0
    targets: list[str] = field(default_factory=list)


def twin_of(path: Path) -> Path:
    """README.md ↔ README.pt-BR.md."""
    name = path.name
    if name.endswith(PT_SUFFIX):
        return path.with_name(name[: -len(PT_SUFFIX)] + ".md")
    return path.with_name(name[: -len(".md")] + PT_SUFFIX)


def parse(text: str) -> Structure:
    structure = Structure()
    fence: str | None = None
    for line in text.splitlines():
        if not structure.switcher and line.strip():
            structure.switcher = line.strip()
        opened = _FENCE.match(line)
        if fence is not None:
            if opened and opened.group(1)[0] == fence[0] and len(opened.group(1)) >= len(fence) and not opened.group(2):
                fence = None
            continue
        if opened:
            fence = opened.group(1)
            structure.fences.append(opened.group(2) or "-")
            continue
        heading = _HEADING.match(line)
        if heading:
            structure.headings.append(len(heading.group(1)))
        for bang, target in _LINK.findall(line):
            structure.targets.append(target)
            structure.images += bool(bang)
        for target in _HTML_IMG.findall(line):
            structure.targets.append(target)
            structure.images += 1
        structure.targets.extend(_HTML_HREF.findall(line))
    return structure


def is_relative(target: str) -> bool:
    return not re.match(r"^([a-z][a-z0-9+.-]*:|#|//)", target, re.IGNORECASE)


def broken_targets(path: Path, structure: Structure) -> list[str]:
    broken = []
    for target in structure.targets:
        if not is_relative(target):
            continue
        local = target.split("#", 1)[0].split("?", 1)[0]
        if local and not (path.parent / local).exists():
            broken.append(target)
    return broken


def markdown_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if any(part in EXEMPT_DIRS for part in relative.parts[:-1]):
            continue
        if relative.as_posix() in EXEMPT_FILES:
            continue
        files.append(path)
    return files


def check_pair(root: Path, english: Path, portuguese: Path) -> list[str]:
    en_rel, pt_rel = english.relative_to(root), portuguese.relative_to(root)
    en, pt = parse(english.read_text(encoding="utf-8")), parse(portuguese.read_text(encoding="utf-8"))
    problems = []
    if f"]({portuguese.name})" not in en.switcher:
        problems.append(f"{en_rel}: the first line must be the language switcher linking to {portuguese.name}")
    if f"]({english.name})" not in pt.switcher:
        problems.append(f"{pt_rel}: the first line must be the language switcher linking to {english.name}")
    if en.headings != pt.headings:
        problems.append(f"{en_rel} ↔ {pt_rel}: heading levels differ ({en.headings} vs {pt.headings})")
    if en.fences != pt.fences:
        problems.append(f"{en_rel} ↔ {pt_rel}: code blocks differ ({en.fences} vs {pt.fences})")
    if en.images != pt.images:
        problems.append(f"{en_rel} ↔ {pt_rel}: image count differs ({en.images} vs {pt.images})")
    for path, rel, structure in ((english, en_rel, en), (portuguese, pt_rel, pt)):
        problems.extend(f"{rel}: broken link {target}" for target in broken_targets(path, structure))
    return problems


def check(root: Path) -> list[str]:
    files = markdown_files(root)
    present = set(files)
    problems = []
    for path in files:
        twin = twin_of(path)
        if path.name.endswith(PT_SUFFIX):
            if twin not in present:
                problems.append(f"{path.relative_to(root)}: orphan translation, {twin.name} does not exist")
            continue
        if twin not in present:
            problems.append(f"{path.relative_to(root)}: missing the pt-BR twin {twin.name}")
            continue
        problems.extend(check_pair(root, path, twin))
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    problems = check(root)
    for problem in problems:
        print(f"::error::{problem}")
    if problems:
        print(f"\n{len(problems)} documentation parity problem(s).")
        print("English is the source of truth; see CONTRIBUTING.md.")
        return 1
    print("Documentation parity: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
