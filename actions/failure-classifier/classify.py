from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

MARKER = "<!-- failure-classification:v1 -->"
MAX_LOG_BYTES = 512 * 1024
FAILURE_CONCLUSIONS = {"failure", "timed_out", "action_required"}
AUTO_PROVEN = "AUTO_PROVEN"
CANDIDATE = "CANDIDATE"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Finding:
    classification: str
    decision: str
    rule: str | None
    basis: str
    candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class FailureRecord:
    workflow_name: str
    run_id: int
    run_url: str
    conclusion: str
    job_name: str
    step_name: str
    finding: Finding


def _contains(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def classify_failure(workflow_name: str, job_name: str, step_name: str, log_text: str) -> Finding:
    combined = "\n".join([workflow_name, job_name, step_name, log_text])

    if _contains(r"failure (?:triage|declaration):\s*FAIL:", combined) or _contains(
        r"missing or duplicated failure-triage v1 block|expected exactly one checkbox for|triage fields are out of canonical order",
        combined,
    ):
        return Finding(
            classification="evidence defect",
            decision=AUTO_PROVEN,
            rule="FC-EVIDENCE-001",
            basis="The failure is emitted by the canonical PR failure-declaration validator before product code or tests establish another responsibility layer.",
        )

    name = f"{workflow_name} {job_name} {step_name}".casefold()
    if any(token in name for token in ("test", "spec", "e2e", "integration")) or _contains(
        r"assertion(?:error| failed)|\bexpected\b.*\bactual\b|tests? failed|failures?:\s*[1-9]",
        log_text,
    ):
        return Finding(
            classification="UNKNOWN",
            decision=CANDIDATE,
            rule=None,
            basis="A test-path failure is observed, but the evidence does not prove whether the implementation or the test expectation owns the defect.",
            candidates=("implementation defect", "test defect"),
        )

    if any(token in name for token in ("compile", "build", "gradle", "cargo", "maven", "npm", "pnpm")):
        return Finding(
            classification="UNKNOWN",
            decision=CANDIDATE,
            rule=None,
            basis="A build-path failure is observed, but implementation, workflow configuration, and execution environment have not been excluded.",
            candidates=("implementation defect", "workflow-policy drift", "environment failure"),
        )

    if any(token in name for token in ("policy", "hardening", "repository drift", "workflow security", "dependency review")):
        return Finding(
            classification="UNKNOWN",
            decision=CANDIDATE,
            rule=None,
            basis="A policy-oriented check failed, but the log has not established whether the repository violates policy or the workflow/evidence itself is defective.",
            candidates=("workflow-policy drift", "evidence defect", "implementation defect"),
        )

    return Finding(
        classification="UNKNOWN",
        decision=UNKNOWN,
        rule=None,
        basis="The available machine evidence is insufficient to establish a single responsibility layer.",
    )


class GitHubApi:
    def __init__(self, repository: str, token: str, api_url: str = "https://api.github.com") -> None:
        self.repository = repository
        self.token = token
        self.api_url = api_url.rstrip("/")

    def _request(self, method: str, path: str, payload: dict | None = None, accept: str = "application/vnd.github+json"):
        url = path if path.startswith("http") else f"{self.api_url}{path}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", accept)
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "luceat-lux-vestra-failure-classifier")
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, payload: dict):
        return self._request("POST", path, payload)

    def patch(self, path: str, payload: dict):
        return self._request("PATCH", path, payload)

    def read_job_log(self, job_id: int) -> str:
        url = f"{self.api_url}/repos/{self.repository}/actions/jobs/{job_id}/logs"
        request = urllib.request.Request(url, method="GET")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "luceat-lux-vestra-failure-classifier")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                head = bytearray()
                tail = bytearray()
                total = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if len(head) < 128 * 1024:
                        need = 128 * 1024 - len(head)
                        head.extend(chunk[:need])
                    tail.extend(chunk)
                    if len(tail) > 384 * 1024:
                        del tail[:-384 * 1024]
                if total > MAX_LOG_BYTES:
                    raw = bytes(head) + b"\n...[log truncated]...\n" + bytes(tail)
                else:
                    overlap = max(0, len(head) + len(tail) - total)
                    raw = bytes(head) + bytes(tail[overlap:])
                return raw.decode("utf-8", errors="replace")
        except (urllib.error.HTTPError, urllib.error.URLError):
            return ""


def _latest_runs(runs: Iterable[dict], tracked: set[str]) -> list[dict]:
    latest: dict[int | str, dict] = {}
    for run in runs:
        name = run.get("name") or "<unnamed>"
        if tracked and name not in tracked:
            continue
        if run.get("event") == "workflow_run" or name == "Failure classification":
            continue
        key = run.get("workflow_id") or name
        current = latest.get(key)
        if current is None or (run.get("run_number", 0), run.get("run_attempt", 0)) > (
            current.get("run_number", 0), current.get("run_attempt", 0)
        ):
            latest[key] = run
    return sorted(latest.values(), key=lambda item: item.get("name") or "")


def _failed_step(job: dict) -> str:
    for step in job.get("steps") or []:
        if step.get("conclusion") in FAILURE_CONCLUSIONS:
            return step.get("name") or "<failed step>"
    return "<job failure>"


def collect_records(api: GitHubApi, runs: list[dict]) -> tuple[list[FailureRecord], list[str]]:
    records: list[FailureRecord] = []
    pending: list[str] = []
    for run in runs:
        name = run.get("name") or "<unnamed>"
        status = run.get("status")
        conclusion = run.get("conclusion")
        if status != "completed":
            pending.append(name)
            continue
        if conclusion not in FAILURE_CONCLUSIONS:
            continue
        jobs_doc = api.get(f"/repos/{api.repository}/actions/runs/{run['id']}/jobs?filter=latest&per_page=100") or {}
        failed_jobs = [job for job in jobs_doc.get("jobs", []) if job.get("conclusion") in FAILURE_CONCLUSIONS]
        if not failed_jobs:
            finding = classify_failure(name, "<workflow>", "<workflow failure>", "")
            records.append(
                FailureRecord(name, int(run["id"]), run.get("html_url") or "", conclusion, "<workflow>", "<workflow failure>", finding)
            )
            continue
        for job in failed_jobs:
            log_text = api.read_job_log(int(job["id"]))
            step_name = _failed_step(job)
            finding = classify_failure(name, job.get("name") or "<job>", step_name, log_text)
            records.append(
                FailureRecord(
                    workflow_name=name,
                    run_id=int(run["id"]),
                    run_url=run.get("html_url") or "",
                    conclusion=conclusion,
                    job_name=job.get("name") or "<job>",
                    step_name=step_name,
                    finding=finding,
                )
            )
    return records, pending


def safe_text(value: str, limit: int = 160) -> str:
    value = re.sub(r"[\r\n\t]+", " ", value or "")
    value = re.sub(r"[<>]", "", value)
    value = value.replace("|", "\\|").strip()
    if len(value) > limit:
        value = value[: limit - 1] + "…"
    return value or "<unnamed>"


def render_report(head_sha: str, records: list[FailureRecord], pending: list[str]) -> str:
    state = "BLOCKED" if records else ("PENDING" if pending else "CLEAR")
    lines = [
        MARKER,
        "## CI Failure Classification",
        "",
        f"**HEAD:** `{head_sha}`  ",
        f"**State:** **{state}**  ",
        f"**Active classified failures:** {len(records)}",
        "",
    ]
    if records:
        lines.extend([
            "| Workflow | Job / step | Classification | Decision |",
            "|---|---|---|---|",
        ])
        for record in records:
            workflow_name = safe_text(record.workflow_name)
            workflow = f"[{workflow_name}]({record.run_url})" if record.run_url else workflow_name
            job_step = f"{safe_text(record.job_name)} / {safe_text(record.step_name)}"
            lines.append(
                f"| {workflow} | {job_step} | `{record.finding.classification}` | `{record.finding.decision}` |"
            )
        lines.append("")
        for index, record in enumerate(records, start=1):
            lines.extend([
                f"### {index}. {safe_text(record.workflow_name)} — {safe_text(record.job_name)}",
                "",
                f"- **Observed:** `{safe_text(record.conclusion)}` at `{safe_text(record.step_name)}`.",
                f"- **Classification:** `{record.finding.classification}`.",
                f"- **Decision:** `{record.finding.decision}`.",
            ])
            if record.finding.rule:
                lines.append(f"- **Rule:** `{record.finding.rule}`.")
            lines.append(f"- **Basis:** {record.finding.basis}")
            if record.finding.candidates:
                lines.append("- **Candidates:** " + ", ".join(f"`{item}`" for item in record.finding.candidates) + ".")
            lines.append("")
    else:
        lines.append("No active failed workflow is established for this exact HEAD.")
        lines.append("")

    if pending:
        lines.append("**Pending workflows:** " + ", ".join(f"`{safe_text(item)}`" for item in sorted(set(pending))) + ".")
        lines.append("")

    lines.extend([
        "> `UNKNOWN` and `CANDIDATE` do not authorize remediation. Establish root cause and complete the PR failure-remediation declaration before changing the owning layer.",
        "",
        "This report is derived from GitHub Actions metadata and bounded log inspection. It never executes PR code or downloaded artifacts.",
    ])
    return "\n".join(lines)


def upsert_comment(api: GitHubApi, pr_number: int, body: str) -> None:
    page = 1
    found_id = None
    while page <= 10:
        comments = api.get(f"/repos/{api.repository}/issues/{pr_number}/comments?per_page=100&page={page}") or []
        for comment in comments:
            if MARKER in (comment.get("body") or ""):
                found_id = comment.get("id")
                break
        if found_id or len(comments) < 100:
            break
        page += 1
    if found_id:
        api.patch(f"/repos/{api.repository}/issues/comments/{found_id}", {"body": body})
    else:
        api.post(f"/repos/{api.repository}/issues/{pr_number}/comments", {"body": body})


def write_summary(body: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(body)
            handle.write("\n")


def write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    repository = os.environ.get("GITHUB_REPOSITORY") or ""
    token = os.environ.get("INPUT_GITHUB_TOKEN") or ""
    tracked = {line.strip() for line in (os.environ.get("INPUT_TRACKED_WORKFLOWS") or "").splitlines() if line.strip()}
    if not event_path or not repository or not token:
        print("failure classifier: missing event path, repository, or token", file=sys.stderr)
        return 2

    with open(event_path, encoding="utf-8") as handle:
        event = json.load(handle)
    trigger = event.get("workflow_run") or {}
    prs = trigger.get("pull_requests") or []
    if not prs:
        body = render_report(trigger.get("head_sha") or "unknown", [], []) + "\n\n_No associated pull request; comment update skipped._"
        write_summary(body)
        print("failure classifier: no associated PR; skipped comment")
        return 0

    pr_number = int(prs[0]["number"])
    api = GitHubApi(repository, token, os.environ.get("GITHUB_API_URL") or "https://api.github.com")
    pr = api.get(f"/repos/{repository}/pulls/{pr_number}")
    current_sha = ((pr or {}).get("head") or {}).get("sha")
    trigger_sha = trigger.get("head_sha")
    if not current_sha:
        print("failure classifier: unable to resolve current PR HEAD", file=sys.stderr)
        return 2
    if trigger_sha != current_sha:
        body = f"{MARKER}\n## CI Failure Classification\n\nStale trigger ignored: `{trigger_sha}` is not current PR HEAD `{current_sha}`."
        write_summary(body)
        print(f"failure classifier: stale trigger {trigger_sha}; current head {current_sha}; no comment mutation")
        return 0

    query = urllib.parse.urlencode({"head_sha": current_sha, "per_page": 100})
    runs_doc = api.get(f"/repos/{repository}/actions/runs?{query}") or {}
    runs = _latest_runs(runs_doc.get("workflow_runs") or [], tracked)
    records, pending = collect_records(api, runs)
    report = render_report(current_sha, records, pending)
    write_summary(report)
    if (os.environ.get("INPUT_COMMENT") or "true").casefold() == "true":
        upsert_comment(api, pr_number, report)

    write_output("state", "blocked" if records else ("pending" if pending else "clear"))
    write_output("active-failures", str(len(records)))
    print(f"failure classifier: report updated for PR #{pr_number} at {current_sha}; failures={len(records)} pending={len(pending)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
