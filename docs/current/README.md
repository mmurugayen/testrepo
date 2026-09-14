# Current documentation: testrepo

Last source review: **2026-09-14**, default branch `main`, commit [`89795c0961a9`](https://github.com/mmurugayen/testrepo/commit/89795c0961a9feb3fa4e4a2c63018b39fa1a86da). This records a documentation review of the linked source snapshot.

Reviewed 2026-09-14 against `05ff385f52d4a7c73a7b3f989ac8cfc8d02e4c25`. The source contains a diagnostic utility; no domain product or Terraform resources are declared.

- [Architecture](ARCHITECTURE.md)
- [Workflow](WORKFLOWS.md)
- [Audit and complete inventory](DOCUMENTATION_AUDIT.md)
- [Validation](VALIDATION.md)
- [Repository README](../../README.md)

## Maintaining the diagrams

Edit [diagrams.json](diagrams/diagrams.json), then run `python3 docs/current/diagrams/render.py`. Commit sources and generated SVGs together.

Check reproducibility with `python3 docs/current/diagrams/render.py --check`. Architecture `units` contain components; workflow `nodes` describe actions and alternatives. Refresh the source commit after comparing implementation changes.
