# testrepo: diagnostic utility architecture

![Component and trust boundaries](diagrams/observability-architecture.svg)

This component map shows the diagnostic utility implemented in this repository. It does not represent a Terraform or domain application deployment.

| Component | Responsibility |
| --- | --- |
| MCP client and stdio adapter | JSON-RPC transport and bounded tool inputs; `scripts/gysam_observability.py` |
| Configured local log sources | Protected JSONL files, selected by the operator; no arbitrary client-selected paths |
| Diagnostic reader and tracing contract | Sanitize, correlate and group evidence; `scripts/gysam_diagnostics.py` and `scripts/gysam_diagnostic_contract.py` |
| Optional external HPC backend | Authentication, registered recovery plans, independent approval and verified resolution memory; separately installed and configured |

The source example does not establish a running backend. Recovery requires a compatible backend and its migration 017, approved aliases and valid credentials. Local searches remain bounded observations, not a complete incident history. Existing process-local HPC plans and durable resolution memory have different lifetimes.

[Detailed source contract](../OBSERVABILITY_MCP.md) · [Execution workflow](WORKFLOWS.md) · [Editable diagram source](diagrams/diagrams.json)
