## Problem and scope

Link the requirement or issue and describe the intended outcome.

## Changes

Describe the behavior and affected interfaces.

## Preflight before paid CI

Complete static/local checks before pushing a ready candidate. Do not rerun an unchanged failed head.

- [ ] Syntax, compile and import checks pass for changed code and tests.
- [ ] Formatter, linter and static checks pass for changed files.
- [ ] Changed public operations satisfy repository logging and privacy rules.
- [ ] Security-sensitive paths are fail-closed; authorization, input validation, file/path, subprocess/network boundaries and error handling were reviewed.
- [ ] Focused tests pass, including negative and error cases.
- [ ] Duplicate calls, dead code, unused variables/imports and debug output were removed.
- [ ] Workflow/YAML changes were syntax checked where applicable.
- [ ] Failed CI was inspected for the concrete failing step/log before rerun or repair.

## Validation

Record exact candidate revision, local/static checks, focused tests and CI outcomes. Mark queued, skipped, unavailable and failing gates explicitly.

## Security and operations

Describe authorization, fail-closed behavior, logging/privacy, compatibility, rollback and remaining qualification limits.
