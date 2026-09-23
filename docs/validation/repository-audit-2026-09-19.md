# Source and CI audit — 19 September 2026

Reviewed default revision `f0dc0823e764530dc59c3225edd56c7a01ad8c3f` and existing recovery/diagnostic candidate `5d485b283bb6fa4db3ffe22f776a80a4147f30ba` (PR #9). All downloaded files were verified against the GitHub tree's blob hashes before testing. There is no AGENTS.md in either tree. The repository is a standalone Python diagnostic utility; it contains no Terraform resources or deployable application requiring cloud provisioning.

## Findings and changes

The default branch passes its 26 existing tests but does not contain the pending canonical receipt-identity and single-terminal-outcome fixes. This candidate retains the existing reviewed implementation and its regression tests. No shared runtime source or provenance hash is changed by this audit.

Recent automatic observability runs were cancelled after waiting for an unassigned self-hosted runner. Their jobs had no steps and runner ID 0; this is runner availability, not a failing test assertion. The workflow now adds a separate `portable-contracts` job on standard `ubuntu-24.04`, gated to public repositories. It has read-only contents permission, disables persisted checkout credentials, uses local fixtures/loopback HTTP and requires no package installation, cloud credentials, deployed backend or paid runner. The existing self-hosted `diagnostics` job, its labels and trust restriction remain. Hosted results do not satisfy the documented self-hosted or installed-target acceptance gates.

Both jobs discover the entire test suite rather than maintaining a list of filenames and check the two generated architecture/workflow diagrams. README commands use the same complete discovery command.

## Validation performed

| Check | Default branch | Existing candidate |
| --- | --- | --- |
| `python3 -m unittest discover -s tests -v` | 26 passed, no skips | 57 passed, no skips |
| `python3 scripts/check_observability_coverage.py` | Passed | Passed |
| `python3 docs/current/diagrams/render.py --check` | 2 passed | 2 passed |

Contracts cover MCP lifecycle and JSON framing, bounded file reads, strict decoding, log privacy/fingerprints, recovery authorization/receipt identity, operation outcomes/context restoration, and interrupted stderr sink recovery. Tests use temporary files, injected clocks/streams, and loopback HTTP servers. Local evidence does not certify a deployed collector, backend, PostgreSQL, sustained backpressure, native host, cloud provider or recovery runbook.

## Remaining gates

Current-candidate GitHub CI, required review, self-hosted runner capacity, and installed backend/collector qualification remain open. No open standalone GitHub issues were present during review; open items were pull requests. Product backlog acceptance remains qualification-pending. Other pending hygiene/planning PRs retain their independent scope and are not declared resolved by this audit.
