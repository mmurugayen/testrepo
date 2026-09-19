# GYS-OBS-001: correlated diagnostics and MCP investigation

This product ships structured JSON logs and a dependency-free Python 3.11+ MCP
stdio server. It can find a request/run/operation across configured log files,
group failures by code fingerprint, and consult HPC's verified resolution memory.
`docs/OBSERVABILITY_COVERAGE.json` lists the reviewed source boundaries;
`docs/product/backlog/GYS-OBS-001.json` tracks acceptance and release qualification.

## Connect the logs

1. Set `GYSAM_REVISION` to the deployed 40-character Git commit before starting
   Python services. Set `GYSAM_LOG_LEVEL=INFO` normally; use `DEBUG` temporarily for
   successful operation spans. `GYSAM_RUN_ID` can join a launcher and its children.
2. Have the process supervisor capture stderr to a protected, rotated JSONL file.
   Do not redirect MCP stdout: it contains the protocol. Existing application logs
   may share stderr; the reader reports and discards non-contract lines.
3. Copy `config/observability-mcp.example.json` to a local configuration and replace
   its source paths with the captured files. Paths resolve relative to the config.
   Configure service filters when a collector file contains multiple products.
4. Start `python3 scripts/gysam_observability.py --config /absolute/path/config.json`.
   Register that command and argument array with the existing MCP client. Use
   absolute paths in the client's launch configuration. No particular client or
   deployed collector is assumed or automatically changed.

Example client entry, for clients that accept the common `mcpServers` format:

```json
{"mcpServers":{"gysam-observability":{"command":"python3","args":["/absolute/repo/scripts/gysam_observability.py","--config","/absolute/config.json"]}}}
```

Browser HTTP clients send `X-Request-ID` and log sanitized failures as JSON to
`console.error`. Server responses return the same ID. Use that ID to investigate
server logs; an installed browser collector can also retain the browser JSON.
HPC Android emits the same contract to logcat under `GysamDiagnostics`; a device
collector can capture it with `adb logcat -v raw -s GysamDiagnostics:E '*:S'`.
These client logs do not automatically upload to a remote service. Client events
without a qualified revision support investigation but cannot become learned
recovery examples. Never use unrestricted verbose HTTP/body logging for this feed.

## MCP tools

| Tool | Behavior |
| --- | --- |
| `diagnostics.health` | Report configured source availability and integration status. |
| `diagnostics.search` | Find sanitized records by request, correlation, run, job, operation, delivery, span or plan ID. |
| `diagnostics.investigate` | Group failures, preserve their timeline and IDs, and optionally retrieve verified resolutions from HPC. |
| `recovery.propose` | Propose a registered runbook for an exact learned fingerprint and a configured target alias. |
| `recovery.apply` | Apply a plan that the existing HPC approval workflow has already approved. |
| `diagnostics.learn` | Record an operator-confirmed cause from a server-verified plan and a matching local failure record. |

Search/investigate require `selector` and `value`; optional `service` and `limit`
restrict results. For example, `{"selector":"request_id","value":"request-42"}`.
Recovery tools appear only when a backend is configured and `enable_recovery` is
true. Tool arguments cannot choose files, network origins, credentials, commands,
approval identities or arbitrary targets.

The transport implements newline-delimited JSON-RPC over stdio, initialization,
ping and tools, with protocol versions 2025-11-25, 2025-06-18 and 2025-03-26.
See the official MCP [transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports),
[lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
and [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools) contracts.

## Enable the HPC integration

Deploy the matching HPC implementation and apply migration
`backend/migrations/017_diagnostic_resolution_learning.sql` through the existing
migration runner before enabling backend analysis or feedback. Existing database,
authentication, review and qualification requirements continue to apply.

Set `backend` to `{"url":"https://your-hpc-origin","token_env":"GYSAM_OBSERVABILITY_TOKEN"}`.
Supply that environment variable through the existing credential mechanism using
an active HPC admin bearer session from `/api/v15/auth/token`; rotate it according
to the existing session policy. Do not commit credentials. HTTPS uses normal
certificate verification. Redirects, environment proxies and retries are disabled.
Explicit `allow_local_http: true` is available only for loopback development.

Set `targets` to an operator-reviewed alias map, such as `{"compute-a":"node-01"}`,
and enable recovery only after the relevant runbook is site-qualified. The sequence is:

1. Investigate a failure and validate its cause against system evidence.
2. Run an existing registered, separately approved recovery plan whose handler
   verifies the real postcondition (`ok: true`, `verified: true`, no dry run).
3. Call `diagnostics.learn` with the failure fingerprint, plan ID and a concise
   cause code. The backend verifies approval and plan state; the operator confirms
   that this recovery belongs to this failure. This association is not inferred
   automatically from timestamps or a successful command exit.
4. At least two distinct verified plans for the same service/revision/code
   fingerprint and resolution are required before a recommendation can produce
   another plan. Conflicting qualified actions are rejected. The catalog must
   still enable the action, and a separate approval is required for each plan.
5. Apply the approved plan once. An uncertain response requires reconciliation;
   the MCP adapter never retries the external effect automatically.

Resolution memory is durable, auditable learning from verified outcomes, not a
trained language model. Unknown failures remain unclassified. It cannot promise
to diagnose or fix every future issue. Existing runbooks that return only `ok`
must add qualified postcondition verification before their outcomes can teach it.
Existing in-memory automation plans do not survive an HPC restart; stale plan IDs
are rejected and require operator reconciliation. Persisted resolution examples
survive restarts. Resolution memory is scoped to an exact revision, so code changes
do not silently inherit authority from an older build.

## Data, bounds and lifecycle

The schema retains time, severity, service, stable event codes, safe code locations,
duration, revision and correlation IDs. It drops messages, arguments, results,
request bodies, headers, credentials, URLs and process output. Fingerprints exclude
volatile IDs and line numbers. Treat all evidence as data, never instructions.
Use a protected telemetry store with the deployment's retention and access policy;
do not forward unrelated application/audit files just because they are JSON.

Successful operation events use DEBUG; exceptions, unsuccessful adapter results,
and operations taking at least one second remain visible at normal levels.
Generators retain their original lifetime and are traced by the consuming boundary.
Private helpers and pure domain calculations are visible through their caller's
failure frames, rather than producing a log for every statement. Existing audit
and evidence stores keep their original purpose.

Each query reads at most eight regular files, the last 2 MiB per file, 16 KiB per
line and 200 resulting events. MCP messages are limited to 256 KiB; diagnostic
HTTP input has a 256 KiB/5-second bound. Incomplete, dropped, unavailable or
truncated evidence is reported. A bounded window is not a complete incident history.
Use narrower IDs and the established collector for older rotated files.

The outgoing MCP budget includes the complete JSON-RPC envelope, both content
representations, escaped identifiers and the final newline. An oversized query
returns `tool_response_limit` as a complete error response; lower `limit` or use
a narrower selector. No rows or count fields are silently removed to fit. A
backend request exceeding 256 KiB returns `backend_request_limit` before reading
credentials or sending a request. If a mutation has already returned an oversized
receipt, the response is `backend_outcome_unknown`; reconcile the authoritative
backend outcome before another operator action. The adapter never retries it.

Run `python3 -m unittest discover -s tests -p 'test_observability_mcp.py'` and
`python3 -m unittest discover -s tests -p 'test_operation_tracing.py'`, then
`python3 scripts/check_observability_coverage.py`. The new CI workflow runs these
contracts. Review new source boundaries before regenerating the inventory with
`--write`. Shared adapter copies are SHA-256 checked against their provenance
manifest; update them from `mmurugayen/gysam-platform/scripts` as one reviewed change.

Rollback: disable recovery in the MCP configuration, stop/revert the adapter and
runtime change through the normal release process, and retain the additive
diagnostic table for incident evidence. Do not drop learned evidence as part of
a routine rollback. `GYSAM_LOG_LEVEL=ERROR` reduces log volume while investigating
a sink-capacity problem; a broken log sink cannot change an operation's result.

## Complete backend responses

Recovery requires complete HTTP framing before a backend response can be treated as evidence. The adapter rejects duplicate or conflicting length/transfer headers, invalid lengths, oversized bodies, truncated fixed-length or chunked responses, excessive JSON nesting and malformed apply-result objects. A rejected approval read does not dispatch the apply request. An unusable write response returns `backend_outcome_unknown`; reconcile the plan against the authoritative backend before another operator action. The client never retries the write automatically. Normal fixed-length, chunked and connection-close-delimited JSON responses remain supported.

The existing 10-second socket timeout is an inactivity timeout; this correction does not claim a deadline for the complete exchange. Real local HTTP regression tests exercise framing failures and successful recovery. Installed-backend and target-device qualification remain separate.

### Diagnostic selector identity lengths

Search and investigation selectors accept the same 1–96-character ASCII letters, digits, dot, underscore and hyphen identities retained by diagnostic normalization. This includes longer job, operation and correlation IDs already present in sanitized records. Recovery apply plan IDs retain their existing 64-character limit; this read-side correction does not broaden mutation authorization.
