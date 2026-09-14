# Documentation integration

Reconciled documentation PR #4 with `main` commit [`05ff385f52d4`](https://github.com/mmurugayen/testrepo/commit/05ff385f52d4a7c73a7b3f989ac8cfc8d02e4c25) on 2026-09-14.

The original documentation revision is [`761754c274bc`](https://github.com/mmurugayen/testrepo/commit/761754c274bcd8742220aa90a244a6eee9597e85). Its inventory and validation records describe that earlier snapshot and remain historical evidence.

## Preserved behavior

All runtime source, workflows, dependency pins and existing default-branch files outside documentation are retained byte-for-byte. README navigation includes the merged [diagnostics and MCP investigation](../OBSERVABILITY_MCP.md), [coverage inventory](../OBSERVABILITY_COVERAGE.json) and [feature backlog](../product/backlog/GYS-OBS-001.md). Diagnostics use fixed source configuration and existing authorization; documentation does not grant recovery or execution authority.

The README describes the current source rather than the earlier placeholder state. Original architecture diagrams remain scoped to the product components they depict; diagnostic setup is described by the linked guide.

## Validation scope

See [merge-reconciliation.json](merge-reconciliation.json) for source preservation and documentation checks. Original product acceptance records retain their dates. Local documentation checks do not substitute for current-head CI, installed clients, collector connectivity, matching server migrations or site-qualified recovery handlers. Review and normal merge controls remain required.
