#!/usr/bin/env python3
"""Repository syntax checks and changed-code logging enforcement."""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXCLUDED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "vendor", "dist", "build",
    "__pycache__", ".tox", ".mypy_cache", ".ruff_cache",
}
TEST_PARTS = {"test", "tests", "fixtures"}
LOGGER_NAMES = {"log", "logger", "LOGGER"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True
    )
    return [
        Path(item.decode())
        for item in result.stdout.split(b"\0")
        if item and not any(part in EXCLUDED_PARTS for part in Path(item.decode()).parts)
    ]


def changed_files(base: str | None, files: list[Path]) -> set[Path]:
    if not base:
        return set()
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = set(files)
    return {Path(line) for line in result.stdout.splitlines() if Path(line) in tracked}


def is_production_python(path: Path) -> bool:
    return (
        path.suffix == ".py"
        and path.as_posix() != "scripts/quality_gate.py"
        and not any(part.lower() in TEST_PARTS for part in path.parts)
    )


def has_log_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if not isinstance(child, ast.Call) or not isinstance(child.func, ast.Attribute):
            continue
        owner = child.func.value
        if isinstance(owner, ast.Name) and owner.id in LOGGER_NAMES:
            return True
        if isinstance(owner, ast.Attribute) and owner.attr.lower() in LOGGER_NAMES:
            return True
    return False


def logging_errors(path: Path, tree: ast.AST) -> list[str]:
    errors: list[str] = []
    has_module_logger = any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id in LOGGER_NAMES
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        )
        for node in getattr(tree, "body", [])
    )
    public = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
        and len(node.body) > 1
    ]
    if public and not has_module_logger:
        errors.append(f"{path}: module has public functionality but no module logger")
    for node in public:
        if not has_log_call(node):
            errors.append(
                f"{path}:{node.lineno}: public callable {node.name!r} has no log outcome"
            )
    return errors


def run_optional(command: list[str], paths: list[Path], label: str) -> list[str]:
    if not paths or shutil.which(command[0]) is None:
        return []
    errors: list[str] = []
    for path in paths:
        result = subprocess.run([*command, str(path)], capture_output=True, text=True)
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            errors.append(f"{label} failed for {path}: {detail}")
    return errors


def validate(base: str | None) -> list[str]:
    files = tracked_files()
    changed = changed_files(base, files)
    errors: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            if path.suffix == ".py":
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                if path in changed and is_production_python(path):
                    errors.extend(logging_errors(path, tree))
            elif path.suffix == ".json":
                json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
    errors.extend(run_optional(["bash", "-n"], [p for p in files if p.suffix == ".sh"], "bash syntax"))
    errors.extend(run_optional(["node", "--check"], [p for p in files if p.suffix in {".js", ".mjs", ".cjs"}], "JavaScript syntax"))
    formatter = shutil.which("tofu") or shutil.which("terraform")
    terraform_files = [p for p in files if p.suffix == ".tf"]
    if formatter and terraform_files:
        result = subprocess.run([formatter, "fmt", "-check", "-recursive"], capture_output=True, text=True)
        if result.returncode:
            errors.append("Terraform/OpenTofu formatting failed: " + (result.stdout or result.stderr).strip())
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", help="base revision used for changed-code logging checks")
    args = parser.parse_args()
    failures = validate(args.base)
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if failures:
        print(f"quality gate failed with {len(failures)} issue(s)", file=sys.stderr)
        return 1
    print("quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
