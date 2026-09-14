# testrepo: diagnostic utility architecture

Last source review: **2026-09-14**, default branch `main`, commit [`89795c0961a9`](https://github.com/mmurugayen/testrepo/commit/89795c0961a9feb3fa4e4a2c63018b39fa1a86da). This records a documentation review of the linked source snapshot.

The primary figure uses nested component cards inside explicit process, source, storage and external-system boundaries. Solid lines identify runtime interfaces or data access; dashed lines identify source/configuration dependencies. Execution order is documented separately in [workflows](WORKFLOWS.md).

![Component and trust boundaries](diagrams/observability-architecture.svg)

This component map shows the diagnostic utility implemented in this repository. It does not represent a Terraform or domain application deployment.

| Component | Responsibility |
| --- | --- |
| MCP client and stdio adapter | JSON-RPC transport and bounded tool inputs; `scripts/gysam_observability.py` |
| Configured local log sources | Protected JSONL files, selected by the operator; no arbitrary client-selected paths |
| Log reader and diagnostic contract | `LogReader` in `scripts/gysam_observability.py` reads bounded log windows; `scripts/gysam_diagnostic_contract.py` sanitizes and correlates evidence |
| Optional external HPC backend | Authentication, registered recovery plans, independent approval and verified resolution memory; separately installed and configured |

The source example does not establish a running backend. Recovery requires a compatible backend and its migration 017, approved aliases and valid credentials. Local searches remain bounded observations, not a complete incident history. Existing process-local HPC plans and durable resolution memory have different lifetimes.

[Detailed source contract](../OBSERVABILITY_MCP.md) · [Execution workflow](WORKFLOWS.md) · [Editable diagram source](diagrams/diagrams.json)
