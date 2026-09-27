from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

API_HOST = "api.typesafe.ai"
API_URL = f"https://{API_HOST}/v1/systemone"
MODEL = "jev-1.13.0"
MAX_REQUEST_BYTES = 512_000
MAX_RESPONSE_BYTES = 1_000_000
TIMEOUT_SECONDS = 45

server = FastMCP("moreno-jev")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _estimate_json_bytes(value: Any) -> int:
    if value is None:
        return 4
    if isinstance(value, bool):
        return 4 if value else 5
    if isinstance(value, int):
        digits = max(1, (abs(value).bit_length() * 30_103 + 99_999) // 100_000)
        return digits + (value < 0)
    if isinstance(value, float):
        return len(repr(value))
    if isinstance(value, str):
        size = 2
        for character in value:
            codepoint = ord(character)
            if character in ('"', "\\", "\\b", "\\f", "\\n", "\\r", "\\t"):
                size += 2
            elif codepoint < 0x20:
                size += 6
            elif 0xD800 <= codepoint <= 0xDFFF:
                raise ValueError("Text contains an invalid Unicode surrogate.")
            elif codepoint <= 0x7F:
                size += 1
            elif codepoint <= 0x7FF:
                size += 2
            elif codepoint <= 0xFFFF:
                size += 3
            else:
                size += 4
            if size > MAX_REQUEST_BYTES:
                return size
        return size
    if isinstance(value, list):
        size = 2 + max(0, len(value) - 1)
        for item in value:
            size += _estimate_json_bytes(item)
            if size > MAX_REQUEST_BYTES:
                return size
        return size
    if isinstance(value, dict):
        size = 2 + max(0, len(value) - 1)
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be text.")
            size += _estimate_json_bytes(key) + 1 + _estimate_json_bytes(item)
            if size > MAX_REQUEST_BYTES:
                return size
        return size
    raise ValueError("state and questions must contain JSON-compatible values.")


def _evaluate(state: str | dict[str, Any] | list[Any], questions: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise RuntimeError("TYPESAFE_API_KEY is missing from the MCP process environment.")
    if not isinstance(state, (str, dict, list)):
        raise ValueError("state must be text, an object, or an array.")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a non-empty object.")
    payload = {"model": MODEL, "state": state, "questions": questions}
    if _estimate_json_bytes(payload) > MAX_REQUEST_BYTES:
        raise ValueError("Request is larger than 512 KB; send a smaller code excerpt or split the review.")
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("Request is larger than 512 KB; send a smaller code excerpt or split the review.")
    request = urllib.request.Request(API_URL, data=body, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, method="POST")
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            response_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(response_body) > MAX_RESPONSE_BYTES:
                raise RuntimeError("TypeSafe returned a response larger than 1 MB.")
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"TypeSafe API returned HTTP {status}.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise RuntimeError("The request to TypeSafe failed or timed out.") from None
    try:
        result = json.loads(response_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("TypeSafe returned an invalid JSON response.") from None
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise RuntimeError("TypeSafe returned an unexpected response shape.")
    return result


@server.tool()
def jev_evaluate(state: Any, questions: dict[str, Any]) -> dict[str, Any]:
    """Evaluate text or structured state with Jev typed questions; submitted state is sent to TypeSafe."""
    return _evaluate(state, questions)


@server.tool()
def jev_review_code(code: str, language: str = "unspecified", context: str = "", focus: str = "") -> dict[str, Any]:
    """Run a structured Jev triage on the supplied code; code and context are sent to TypeSafe."""
    state = {"language": language, "code": code, "context": context}
    scope = focus or "the supplied code and relevant context"
    return _evaluate(
        state,
        {
            "has_concrete_bug": {
                "type": "noul",
                "instructions": f"Does {scope} contain a concrete correctness, security, reliability, or portability bug rather than a style concern?",
            },
            "primary_category": {
                "type": "choice",
                "instructions": f"What category best describes the most important concrete issue in {scope}?",
                "criteria": {
                    "correctness": "Incorrect behavior or a failure for valid inputs.",
                    "security": "A vulnerability or unsafe handling of data or permissions.",
                    "reliability": "A failure, hang, race, or resource problem.",
                    "portability": "Behavior that breaks on a supported platform.",
                    "performance": "A material performance problem.",
                    "none": "No concrete issue is apparent.",
                    "other": "A concrete issue outside the listed categories.",
                },
            },
            "severity": {
                "type": "score",
                "instructions": f"Rate the most severe concrete issue in {scope}.",
                "criteria": ["No concrete issue", "Minor edge case", "Major functional failure", "Critical widespread failure"],
            },
            "needs_human_review": {
                "type": "noul",
                "instructions": f"Should a human inspect {scope} before relying on it?",
            },
        },
    )


@server.tool()
def jev_review_diff(diff: str, language: str = "unspecified", context: str = "", focus: str = "") -> dict[str, Any]:
    """Check a proposed diff for concrete regressions; the diff and context are sent to TypeSafe."""
    state = {"language": language, "diff": diff, "context": context, "focus": focus}
    return _evaluate(
        state,
        {
            "introduces_concrete_bug": {
                "type": "noul",
                "instructions": "Does the supplied diff introduce a concrete correctness, security, reliability, or portability bug?",
            },
            "primary_category": {
                "type": "choice",
                "instructions": "What category best describes the most important concrete issue introduced by the diff?",
                "criteria": {
                    "correctness": "Incorrect behavior or a failure for valid inputs.",
                    "security": "A vulnerability or unsafe handling of data or permissions.",
                    "reliability": "A failure, hang, race, or resource problem.",
                    "portability": "Behavior that breaks on a supported platform.",
                    "performance": "A material performance problem.",
                    "none": "No concrete issue is apparent.",
                    "other": "A concrete issue outside the listed categories.",
                },
            },
            "severity": {
                "type": "score",
                "instructions": "Rate the most severe concrete issue introduced by the diff.",
                "criteria": ["No concrete issue", "Minor edge case", "Major functional failure", "Critical widespread failure"],
            },
            "needs_human_review": {
                "type": "noul",
                "instructions": "Should a human inspect this diff before relying on it?",
            },
        },
    )


@server.tool()
def jev_check_hypothesis(code: str, hypothesis: str, symptom: str = "", language: str = "unspecified", context: str = "") -> dict[str, Any]:
    """Estimate whether a debugging hypothesis fits the supplied symptom and code; inputs are sent to TypeSafe."""
    state = {"language": language, "code": code, "hypothesis": hypothesis, "symptom": symptom, "context": context}
    return _evaluate(
        state,
        {
            "hypothesis_supported": {
                "type": "noul",
                "instructions": "Does the stated hypothesis plausibly explain the stated symptom given the supplied code and context?",
            },
            "evidence_sufficient": {
                "type": "noul",
                "instructions": "Is the supplied code and context sufficient to assess whether the hypothesis explains the symptom?",
            },
        },
    )


@server.tool()
def jev_review_test_output(output: str, command: str = "", language: str = "", context: str = "") -> dict[str, Any]:
    """Classify supplied build or test output; the log and context are sent to TypeSafe."""
    state = {"command": command, "language": language, "output": output, "context": context}
    return _evaluate(
        state,
        {
            "failure_class": {
                "type": "choice",
                "instructions": "What kind of failure is best supported by the supplied build or test output?",
                "criteria": {
                    "compile": "A compiler or type-checking failure.",
                    "link": "A linker or symbol-resolution failure.",
                    "test_assertion": "A test ran and an assertion or expected result failed.",
                    "runtime": "The program crashed or failed during execution.",
                    "timeout_or_flake": "The failure appears intermittent, timing-related, or a timeout.",
                    "environment_or_dependency": "The output points to a missing tool, dependency, configuration, or environment problem.",
                    "other": "A different failure type.",
                    "unclear": "The output is insufficient to classify the failure.",
                },
            },
            "likely_code_regression": {
                "type": "noul",
                "instructions": "Does the supplied output provide evidence of a code regression rather than only an environment or tooling problem?",
            },
            "severity": {
                "type": "score",
                "instructions": "Rate the impact of the failure on the affected development or runtime workflow.",
                "criteria": ["Informational", "Minor", "Major", "Blocking"],
            },
            "evidence_sufficient": {
                "type": "noul",
                "instructions": "Is the supplied output and context sufficient to identify the failure class with useful confidence?",
            },
        },
    )


@server.tool()
def jev_triage_bug_report(report: str, context: str = "") -> dict[str, Any]:
    """Triage a supplied bug report into typed category, impact, and reproduction signals."""
    state = {"report": report, "context": context}
    return _evaluate(
        state,
        {
            "issue_type": {
                "type": "choice",
                "instructions": "What kind of request or issue is described?",
                "criteria": {
                    "correctness_bug": "The software behaves incorrectly or fails.",
                    "security_issue": "The report describes a security or data-protection risk.",
                    "performance_issue": "The main concern is speed, resource use, or responsiveness.",
                    "compatibility_issue": "The problem depends on an operating system, runtime, dependency, or integration.",
                    "usability_issue": "The software works but is confusing or difficult to use.",
                    "feature_request": "The report requests new behavior rather than describing a defect.",
                    "unclear": "The report does not contain enough information to classify.",
                },
            },
            "severity": {
                "type": "score",
                "instructions": "Rate the user impact described in the report, not the effort required to fix it.",
                "criteria": ["No demonstrated impact", "Low impact or workaround exists", "Moderate impact", "High impact or core workflow blocked", "Critical widespread or data-loss impact"],
            },
            "reproduction_clarity": {
                "type": "score",
                "instructions": "How clearly can the described behavior be reproduced from the report and context?",
                "criteria": ["No reproducible detail", "Vague symptoms", "Some steps or conditions", "Clear repeatable steps", "Minimal reproduction with expected and actual results"],
            },
            "needs_followup": {
                "type": "noul",
                "instructions": "Should the reporter be asked for more diagnostic information before the issue is assigned or fixed?",
            },
        },
    )


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
