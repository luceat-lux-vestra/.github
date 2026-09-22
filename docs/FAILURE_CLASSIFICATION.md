# Failure classification

The failure-classification system separates observation, classification, and remediation.

## Invariants

- A failed check is an observation, not a root cause.
- `UNKNOWN`, `UNVERIFIED`, and insufficient evidence remain fail-closed.
- Only deterministic rules that establish a single responsibility layer may emit `AUTO_PROVEN`.
- `CANDIDATE` may narrow investigation but never authorizes remediation.
- The classifier never checks out or executes pull-request code and never executes downloaded artifacts.
- Reports are exact-HEAD scoped. A stale `workflow_run` event may write a job summary but must not mutate the current PR report.
- The current GitHub Actions state is the source of truth; old failures on the same workflow are superseded by the latest run for that workflow on the exact HEAD.

## Canonical classifications

- `implementation defect`
- `test defect`
- `evidence defect`
- `workflow-policy drift`
- `environment failure`
- `UNKNOWN` (classifier observation state only; never a mergeable remediation classification)

## Decision levels

- `AUTO_PROVEN`: deterministic evidence establishes one canonical classification.
- `CANDIDATE`: evidence narrows the plausible responsibility layers, but more than one remains.
- `UNKNOWN`: machine evidence does not materially narrow the responsibility layer.

## Report surfaces

Each classifier run writes the exact-HEAD report to the GitHub Actions job summary. When an associated pull request exists, it also upserts one sticky PR comment marked with `failure-classification:v1`.

The report intentionally does not copy raw log bodies into PR comments. Logs are treated as untrusted input and are only used for bounded pattern inspection.
