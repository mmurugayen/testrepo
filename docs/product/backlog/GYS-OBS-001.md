# GYS-OBS-001 — testrepo

Priority: high. Status: implemented candidate; release/site qualification pending.

Investigating an issue needs stable request/run identifiers and safe code locations
across client, API, worker and integration boundaries. This feature provides the
shared log contract, MCP investigation, verified-resolution feedback and governed
recovery integration. This repository has no pre-existing application runtime. The shared MCP adapter and tracing helper are implemented and tested for future product code.

The [machine-readable feature](GYS-OBS-001.json) contains acceptance criteria.
Follow the [operator guide](../../OBSERVABILITY_MCP.md) to connect the deployed logs
and qualify the HPC backend. Review the [source inventory](../../OBSERVABILITY_COVERAGE.json)
when adding an implementation. This is one cross-product extension feature; it
does not reclassify original source-backed catalog rows as delivered.

Local contract tests are development evidence. Required CI, real PostgreSQL,
collector wiring, installed clients and site-runbook verification remain release
gates. Unknown failures stay unclassified; learned examples do not guarantee that
every future issue can be fixed automatically.
