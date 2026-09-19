# Source and CI audit — 19 September 2026

Reviewed default revision `f0dc0823e764530dc59c3225edd56c7a01ad8c3f` and existing recovery/diagnostic candidate `5d485b283bb6fa4db3ffe22f776a80a4147f30ba` (PR #9). All downloaded files were verified against the GitHub tree's blob hashes before testing. There is no AGENTS.md in either tree. The repository is a standalone Python diagnostic utility; it contains no Terraform resources or deployable application requiring cloud provisioning.

## Findings and changes

The default branch passes its 26 existing tests but does not contain the pending canonical receipt-identity and single-terminal-outcome fixes. The initial CI-only increment retained that existing implementation. The source follow-up below now synchronizes reviewed canonical fixes and matching provenance.

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

## Canonical source follow-up

The continued audit found that malformed backend configuration could expose an uncaught traceback, boolean schema versions were accepted, and nested buffered WSGI wrappers generated different request IDs when the incoming ID was missing or invalid. Inner logs could not be correlated with the returned response ID.

This reviewed source proposal copies four files verbatim from canonical Platform [PR #62](https://github.com/mmurugayen/gysam-platform/pull/62), commit `8e92b4783d5ba97360a9d53364f0ced9b757fcf5`: the MCP adapter/tests and diagnostic helper/new WSGI correlation tests. It combines strict backend origin/port/type validation, integer schema and boolean flag validation, and stable sanitized startup failure with the already reviewed bounded-reader implementation. Nested WSGI layers reuse one normalized request ID while preserving response/body semantics, exceptions, privacy and caller context. The bounded-reader changes and all five existing reader regressions are retained, not overwritten by an older configuration-only source snapshot.

`config/observability-provenance.json` records exact SHA-256 hashes, the prior source hashes, the canonical candidate revision, and `consumer_merge_requires_canonical_merge: true`. Existing product acceptance and prior dependency gates remain intact. The source policy says to review canonical changes, copy them verbatim and refresh hashes together. Canonical review/merge is required before downstream merge qualification; it does not prohibit preparing source proposals for review.

Validation of this complete consumer proposal: **67 Python tests passed, no skips**, and source inventory/provenance matched. The two new WSGI regression methods failed four baseline subcases and both pass after the fix. Tests cover missing/invalid/bytes and valid inbound IDs, nested error paths, response headers, returned body identity, privacy, independent request IDs and context restoration. The canonical MCP module now includes 28 methods; no existing regression was removed.

This remains an unmerged candidate. Platform #62 must pass its canonical gates and merge before this consumer may merge; current consumer hosted/self-hosted CI and review also remain required. The original green hosted run applies to the prior CI-only revision and does not qualify this new head. No default branch, installed backend, native environment or product release acceptance is advanced.
