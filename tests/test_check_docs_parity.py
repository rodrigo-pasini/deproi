from pathlib import Path

import check_docs_parity as parity

EN_SWITCH = "🇺🇸 English · [🇧🇷 Português]({pt})"
PT_SWITCH = "[🇺🇸 English]({en}) · 🇧🇷 Português"


def write_pair(root: Path, name: str, en_body: str, pt_body: str, subdir: str = "") -> None:
    folder = root / subdir
    folder.mkdir(parents=True, exist_ok=True)
    en_name, pt_name = f"{name}.md", f"{name}.pt-BR.md"
    (folder / en_name).write_text(EN_SWITCH.format(pt=pt_name) + "\n\n" + en_body, encoding="utf-8")
    (folder / pt_name).write_text(PT_SWITCH.format(en=en_name) + "\n\n" + pt_body, encoding="utf-8")


def test_twin_of_goes_both_ways():
    assert parity.twin_of(Path("docs/a.md")) == Path("docs/a.pt-BR.md")
    assert parity.twin_of(Path("docs/a.pt-BR.md")) == Path("docs/a.md")


def test_matching_pair_is_clean(tmp_path):
    body = "# Title\n\n## Part\n\n```bash\necho hi\n```\n\n![x](img.svg)\n"
    (tmp_path / "img.svg").write_text("<svg/>")
    write_pair(tmp_path, "README", body, body.replace("Title", "Título"))
    assert parity.check(tmp_path) == []


def test_missing_twin_and_orphan_fail(tmp_path):
    (tmp_path / "README.md").write_text("# x\n")
    (tmp_path / "GUIDE.pt-BR.md").write_text("# x\n")
    problems = parity.check(tmp_path)
    assert any("missing the pt-BR twin README.pt-BR.md" in p for p in problems)
    assert any("orphan translation" in p for p in problems)


def test_switcher_is_required(tmp_path):
    (tmp_path / "A.md").write_text("# A\n")
    (tmp_path / "A.pt-BR.md").write_text("# A\n")
    problems = parity.check(tmp_path)
    assert sum("language switcher" in p for p in problems) == 2


def test_heading_mismatch_fails(tmp_path):
    write_pair(tmp_path, "A", "# A\n\n## B\n", "# A\n")
    assert any("heading levels differ" in p for p in parity.check(tmp_path))


def test_headings_inside_code_fences_are_ignored(tmp_path):
    write_pair(tmp_path, "A", "# A\n\n```bash\n# a shell comment\n```\n", "# A\n\n```bash\n# um comentário\n```\n")
    assert parity.check(tmp_path) == []


def test_code_fence_language_mismatch_fails(tmp_path):
    write_pair(tmp_path, "A", "```bash\nx\n```\n", "```json\nx\n```\n")
    assert any("code blocks differ" in p for p in parity.check(tmp_path))


def test_image_count_mismatch_fails(tmp_path):
    (tmp_path / "a.svg").write_text("<svg/>")
    write_pair(tmp_path, "A", '![a](a.svg)\n<img src="a.svg">\n', "![a](a.svg)\n")
    assert any("image count differs" in p for p in parity.check(tmp_path))


def test_broken_relative_link_fails_but_urls_and_anchors_pass(tmp_path):
    body = "[ok](https://example.com) [anchor](#part) [mail](mailto:a@b.c) [bad](docs/nope.md)\n"
    write_pair(tmp_path, "A", body, body)
    problems = parity.check(tmp_path)
    assert len([p for p in problems if "broken link docs/nope.md" in p]) == 2
    assert not any("example.com" in p or "#part" in p for p in problems)


def test_exempt_files_and_dirs_are_skipped(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("Read AGENTS.md\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.md").write_text("# x\n")
    assert parity.check(tmp_path) == []


def test_pairs_in_subdirectories(tmp_path):
    write_pair(tmp_path, "how-it-works", "# How\n", "# Como\n", subdir="docs")
    assert parity.check(tmp_path) == []


def test_repository_docs_are_in_parity():
    root = Path(__file__).resolve().parent.parent
    assert parity.check(root) == []
