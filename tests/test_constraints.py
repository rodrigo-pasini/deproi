"""Structural guarantees of deproi.py that the security model relies on."""

from __future__ import annotations

import ast
import re
import sys

from conftest import ROOT

import deproi

SOURCE = (ROOT / "deproi.py").read_text()
TREE = ast.parse(SOURCE)


def test_standard_library_only():
    imported = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert imported - set(sys.stdlib_module_names) - {"__future__"} == set()


def test_python_310_syntax():
    ast.parse(SOURCE, feature_version=(3, 10))


def test_self_update_contract_markers():
    assert deproi.SELF_UPDATING is True
    assert callable(deproi.main)
    assert deproi.DEPROI_VERSION.count(".") == 2


def test_no_shell_anywhere():
    assert "shell=True" not in SOURCE
    assert "os.system(" not in SOURCE
    assert "os.popen(" not in SOURCE


def test_never_discards_work_in_the_checkout():
    git_calls = re.findall(r'git_command\(\s*cfg,\s*"([a-z-]+)"', SOURCE)
    assert set(git_calls) == {"fetch", "rev-parse", "status", "show", "merge-base", "merge"}


def test_license_header():
    assert "Copyright (c) 2026 Rodrigo Mendes Pasini" in SOURCE.splitlines()[4]
    assert "MIT License" in SOURCE.splitlines()[5]


def test_main_is_guarded():
    assert SOURCE.rstrip().endswith("sys.exit(entry(sys.argv))")
    assert 'if __name__ == "__main__":' in SOURCE
