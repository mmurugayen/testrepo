# testrepo

Documentation reconciled on **2026-09-14** with `main` at [`05ff385f52d4`](https://github.com/mmurugayen/testrepo/commit/05ff385f52d4a7c73a7b3f989ac8cfc8d02e4c25).

This repository contains a shared diagnostics and MCP investigation foundation. It does not yet define a deployable domain product or Terraform infrastructure module.

## Current contents

| Source | Purpose |
| --- | --- |
| `scripts/gysam_diagnostics.py` and `scripts/gysam_diagnostic_contract.py` | Bounded structured operation diagnostics and their shared contract |
| `scripts/gysam_observability.py` | MCP log investigation and optional verified recovery integration |
| `config/observability-*.json` | Example connection settings, source coverage and provenance |
| `tests/` | Diagnostic and MCP contract tests |
| `.github/workflows/observability.yml` | Self-hosted diagnostic contract validation |

The existing `new/newfile.txt` and `newtestrepo/main.java` files are retained as repository samples.

## Checkout and local validation

```bash
git clone --branch main https://github.com/mmurugayen/testrepo.git
cd testrepo
python3 -m unittest discover -s tests -p test_observability_mcp.py
python3 -m unittest discover -s tests -p test_operation_tracing.py
```

Local contract tests do not establish live collector connectivity, verified recovery or production readiness. Configuration and operating boundaries are documented in the [MCP guide](docs/OBSERVABILITY_MCP.md) and [GYS-OBS-001 backlog](docs/product/backlog/GYS-OBS-001.md).

The [earlier documentation audit](docs/current/DOCUMENTATION_AUDIT.md) describes the original pre-diagnostics snapshot. See the [integration record](docs/current/INTEGRATION.md) for the current reconciliation and validation limits.
