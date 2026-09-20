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
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "vendor",
    "venv",
}
TEST_PARTS = {"fixtures", "test", "tests"}
LOGGER_NAMES = {"LOGGER", "log", "logger"}
LOG_METHODS = {
    "debug", "info", "warning", "warn", "error",
    "exception", "critical", "fatal", "log",
}


def tracked_files() -> list[Path]:
    """Return tracked files outside generated and dependency directories."""
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    paths: list[Path] = []
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        path = Path(item.decode())
        if not any(part in EXCLUDED_PARTS for part in path.parts):
            paths.append(path)
    return paths


def changed_files(base: str | None, files: list[Path]) -> set[Path]:
    """Return tracked files changed since the supplied base revision."""
    if not base:
        return set()
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMR",
            f"{base}...HEAD",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = set(files)
    return {
        Path(line)
        for line in result.stdout.splitlines()
        if Path(line) in tracked
    }


def is_production_python(path: Path) -> bool:
    """Return whether a path contains production Python implementation."""
    return (
        path.suffix == ".py"
        and path.as_posix() != "scripts/quality_gate.py"
        and not any(part.lower() in TEST_PARTS for part in path.parts)
    )


def has_log_call(node: ast.AST) -> bool:
    """Return whether an AST node includes an accepted logger call."""
    pending = list(ast.iter_child_nodes(node))
    while pending:
        child = pending.pop()
        if isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        pending.extend(ast.iter_child_nodes(child))
        if not isinstance(child, ast.Call):
            continue
        if not isinstance(child.func, ast.Attribute):
            continue
        if child.func.attr not in LOG_METHODS:
            continue
        owner = child.func.value
        if isinstance(owner, ast.Name) and owner.id in LOGGER_NAMES:
            return True
        if isinstance(owner, ast.Attribute):
            if owner.attr in LOGGER_NAMES:
                return True
    return False


def assigned_names(node: ast.Assign | ast.AnnAssign) -> list[ast.expr]:
    """Return assignment targets for regular and annotated assignments."""
    if isinstance(node, ast.Assign):
        return list(node.targets)
    return [node.target]


def logging_errors(path: Path, tree: ast.AST) -> list[str]:
    """Return changed-code logging violations for one Python module."""
    errors: list[str] = []
    body = getattr(tree, "body", [])
    has_module_logger = any(
        isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            isinstance(target, ast.Name) and target.id in LOGGER_NAMES
            for target in assigned_names(node)
        )
        for node in body
    )
    public = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
        and len(node.body) > 1
    ]
    if public and not has_module_logger:
        errors.append(
            f"{path}: module has public functionality but no module logger"
        )
    for node in public:
        if not has_log_call(node):
            errors.append(
                f"{path}:{node.lineno}: public callable "
                f"{node.name!r} has no log outcome"
            )
    return errors


def run_optional(
    command: list[str],
    paths: list[Path],
    label: str,
) -> list[str]:
    """Run a syntax command for each path when its runtime is installed."""
    if not paths:
        return []
    if shutil.which(command[0]) is None:
        print(
            f"SKIP: {label}: {command[0]} unavailable; "
            f"{len(paths)} file(s) unverified",
            file=sys.stderr,
        )
        return []
    errors: list[str] = []
    for path in paths:
        result = subprocess.run(
            [*command, str(path)],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            errors.append(f"{label} failed for {path}: {detail}")
    return errors


def validate_files(files: list[Path], changed: set[Path]) -> list[str]:
    """Validate built-in Python and JSON syntax and changed-code logging."""
    errors: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            if path.suffix == ".py":
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
                compile(tree, str(path), "exec")
                if path in changed and is_production_python(path):
                    errors.extend(logging_errors(path, tree))
            elif path.suffix == ".json":
                source = path.read_text(encoding="utf-8")
                json.loads(source)
        except (
            OSError,
            UnicodeError,
            SyntaxError,
            json.JSONDecodeError,
        ) as exc:
            errors.append(f"{path}: {exc}")
    return errors


def validate_terraform(files: list[Path]) -> list[str]:
    """Run repository-wide Terraform/OpenTofu formatting when available."""
    formatter = shutil.which("tofu") or shutil.which("terraform")
    if not any(path.suffix == ".tf" for path in files):
        return []
    if not formatter:
        print(
            "SKIP: Terraform/OpenTofu formatting: formatter unavailable; unverified",
            file=sys.stderr,
        )
        return []
    result = subprocess.run(
        [formatter, "fmt", "-check", "-recursive"],
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stdout or result.stderr).strip()
        return [f"Terraform/OpenTofu formatting failed: {detail}"]
    return []


def validate(base: str | None) -> list[str]:
    """Run all available repository syntax and logging checks."""
    files = tracked_files()
    changed = changed_files(base, files)
    errors = validate_files(files, changed)
    shell_files = [path for path in files if path.suffix == ".sh"]
    script_files = [
        path
        for path in files
        if path.suffix in {".cjs", ".js", ".mjs"}
    ]
    errors.extend(run_optional(["bash", "-n"], shell_files, "bash syntax"))
    errors.extend(
        run_optional(["node", "--check"], script_files, "JavaScript syntax")
    )
    errors.extend(validate_terraform(files))
    return errors


def main() -> int:
    """Run the command-line quality gate."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        help="base revision used for changed-code logging checks",
    )
    args = parser.parse_args()
    failures = validate(args.base)
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    if failures:
        print(
            f"quality gate failed with {len(failures)} issue(s)",
            file=sys.stderr,
        )
        return 1
    print("Available quality checks passed; reported SKIPs remain unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
