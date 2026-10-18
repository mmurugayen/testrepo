# Cost-aware CI policy

This is a review-only policy, not evidence of a completed pipeline optimization.

- Preserve existing mandatory tests, security gates, and release evidence.
- Cancel superseded pull-request runs when safe; retain push and release evidence.
- Use self-hosted infrastructure where required by repository policy.
- Do not introduce paid services or upload artifacts to metered services without approval.
- Limit unnecessary work with safe path scoping and dependency reuse only after verifying required checks are never skipped.
- Use pinned actions, read-only default permissions, bounded timeouts, and no automatic AI repair merges.
- Measure queue time, execution time, cache hit rate, and failed-run rework before changing production workflows.
