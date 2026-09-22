from __future__ import annotations

import os
import re
import sys

START = "<!-- failure-triage:v1:start -->"
END = "<!-- failure-triage:v1:end -->"
NOT_REMEDIATION = "Not remediation for an observed failure"
REMEDIATION = "Remediation for an observed failure"
FIELDS = ["Observed", "Classification", "Basis", "Root cause", "Remediation", "Proof"]
ALLOWED = {
    "implementation defect",
    "test defect",
    "evidence defect",
    "workflow-policy drift",
    "environment failure",
}
SENTINELS = {
    "unknown",
    "unverified",
    "insufficient evidence",
    "tbd",
    "todo",
    "n/a",
    "na",
    "none",
}
TRUSTED_BOT_LOGINS = {"dependabot[bot]"}
UNRESOLVED_ROOT = re.compile(
    r"(?i)^\\s*(?:(?:the\\s+)?(?:root\\s+cause|cause|reason)\\s*(?:is|remains|[:=])\\s*)?"
    r"(?:still\\s+)?(?:unknown|unverified|tbd|todo|insufficient\\s+evidence)\\b"
)


class TriageError(ValueError):
    pass


def clean(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    return value.strip().strip(chr(96)).strip()


def checked(block: str, label: str) -> bool:
    pattern = rf"(?im)^\\s*-\\s*\\[(?P<mark>[ xX])\\]\\s*{re.escape(label)}\\s*$"
    matches = list(re.finditer(pattern, block))
    if len(matches) != 1:
        raise TriageError(f"expected exactly one checkbox for: {label}")
    return matches[0].group("mark").lower() == "x"


def field_values(block: str) -> dict[str, str]:
    matches: dict[str, re.Match[str]] = {}
    for field in FIELDS:
        found = list(re.finditer(rf"(?m)^{re.escape(field)}:\\s*$", block))
        if len(found) != 1:
            raise TriageError(f"expected exactly one '{field}:' field")
        matches[field] = found[0]

    ordered = [matches[field].start() for field in FIELDS]
    if ordered != sorted(ordered):
        raise TriageError("triage fields are out of canonical order")

    values: dict[str, str] = {}
    for index, field in enumerate(FIELDS):
        start = matches[field].end()
        end = matches[FIELDS[index + 1]].start() if index + 1 < len(FIELDS) else len(block)
        values[field] = clean(block[start:end])
    return values


def validate(body: str, author_type: str, author_login: str) -> str:
    if author_type == "Bot" and START not in body and END not in body:
        if author_login.casefold() in TRUSTED_BOT_LOGINS:
            return "bot-exempt"
        raise TriageError(f"untrusted bot requires failure-triage block: {author_login or '<unknown>'}")

    if body.count(START) != 1 or body.count(END) != 1:
        raise TriageError("missing or duplicated failure-triage v1 block")
    start = body.index(START) + len(START)
    end = body.index(END)
    if start >= end:
        raise TriageError("failure-triage markers are out of order")

    block = body[start:end]
    not_remediation = checked(block, NOT_REMEDIATION)
    remediation = checked(block, REMEDIATION)
    if not_remediation == remediation:
        raise TriageError("select exactly one remediation declaration")

    if not_remediation:
        return "not-remediation"

    values = field_values(block)
    for field, value in values.items():
        if not value:
            raise TriageError(f"{field} is required for remediation")
        if value.casefold() in SENTINELS:
            raise TriageError(f"{field} remains fail-closed: {value}")

    classification = values["Classification"].casefold()
    if classification not in ALLOWED:
        raise TriageError(
            "Classification must be exactly one canonical non-UNKNOWN class: "
            + ", ".join(sorted(ALLOWED))
        )
    if UNRESOLVED_ROOT.search(values["Root cause"]):
        raise TriageError("Root cause contains an unresolved marker; remediation remains blocked")

    return f"remediation:{classification}"


def main() -> int:
    body = os.environ.get("INPUT_PR_BODY") or ""
    author_type = os.environ.get("INPUT_PR_AUTHOR_TYPE") or ""
    author_login = os.environ.get("INPUT_PR_AUTHOR_LOGIN") or ""
    try:
        result = validate(body, author_type, author_login)
    except TriageError as exc:
        print(f"failure declaration: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"failure declaration: PASS ({result})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
