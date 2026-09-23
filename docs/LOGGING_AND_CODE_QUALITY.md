# Logging and code-quality standard

This standard applies to all existing and future implementation in `mmurugayen/testrepo`.

## Required implementation logging

Every functional boundary must emit structured, actionable diagnostics:

- create one module logger with `logging.getLogger(__name__)` (or the language-equivalent structured logger);
- record entry/acceptance and one terminal success or failure outcome for externally observable operations;
- use `debug`, `info`, `warning`, `error`, and exception logging according to operational impact;
- include stable event names and safe correlation identifiers when work crosses API, worker, database, scheduler, provider, or deployment boundaries;
- preserve exceptions and uncertain outcomes; never report an operation as successful before its effect is verified;
- never log passwords, tokens, cookies, credentials, authorization headers, private payloads, or unnecessary personal data;
- sanitize command output, provider responses, paths, and exception details before logging;
- use bounded fields and retention so diagnostics cannot grow without control.

Library-style pure helpers may avoid noisy entry/exit messages, but the public functionality that invokes them must log the observable outcome. New or modified nontrivial public Python callables are checked automatically.

The Python gate recognizes module loggers created with an imported `logging.getLogger` factory, including import aliases. Placeholders, bare annotations, unrelated factories and direct reassignment do not count as logger initialization. A single statement containing a call, await, yield, attribute/subscript write or control flow is nontrivial; a simple pure getter remains exempt, with or without a docstring. These are conservative source checks, not proof that every runtime path emits a terminal outcome; dynamic bindings and custom logger factories require separate review.

## Required checks

Every implementation change must pass all applicable checks:

1. Python compilation and AST parsing.
2. Ruff lint across the repository.
3. JavaScript syntax checks when Node.js is available.
4. Bash syntax checks.
5. JSON parsing.
6. Terraform/OpenTofu formatting checks when either tool is available.
7. The repository's existing unit, integration, PostgreSQL, API/browser, security, native, hardware/provider, performance, recovery, and deployment qualification gates.

A missing tool, dependency, self-hosted runner, provider, database, or hardware target is not a pass. Required checks must not be disabled, ignored, downgraded, or hidden. Skips require a documented, reviewed reason and must remain visible.

## Run locally

```bash
python3 scripts/quality_gate.py
python3 -m pip install "ruff==0.13.1"
python3 -m ruff check .
```

To validate logging on changed production Python code against a base revision:

```bash
python3 scripts/quality_gate.py --base origin/main
```

Use the repository's actual default branch where it differs from `main`.

## Legacy implementation

The syntax and Ruff checks intentionally cover existing code. When the gate identifies legacy failures, correct the implementation and add or improve safe structured logging in the touched functional area. Do not add blanket exclusions, broad `noqa` markers, empty exception handlers, fake log calls, or reduced acceptance criteria merely to make CI green.

## Pull-request evidence

A pull request must state:

- functionality changed;
- structured events added or updated;
- sensitive fields explicitly excluded or redacted;
- syntax, lint, tests, and qualification commands run;
- failures, skips, unavailable environments, and remaining native acceptance work.

Merge only after all required checks pass.
