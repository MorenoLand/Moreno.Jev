---
name: jev-review
description: Use TypeSafe Jev for a structured second opinion on code, diffs, or debugging hypotheses when the user asks for Jev review.
---

Use the Moreno.Jev MCP tools only when the user requests Jev or invokes this skill. Send only the relevant code, diff, hypothesis, and context the user intends to share with TypeSafe; do not submit an entire repository by default.

Use `jev_review_code` for a focused code triage, `jev_review_diff` to assess a proposed change, and `jev_check_hypothesis` to evaluate a debugging theory against a symptom. Use `jev_evaluate` for custom Choice, Score, or Noul questions. Jev returns typed judgments and probabilities, not explanations or patches.

If the client exposes MCP through a gateway, discover the Moreno.Jev tools through that gateway and call the returned tool name.

Report the returned answers and probabilities, then inspect any flagged code in repository context. Give the user concrete evidence and a debugging step or fix suggestion; treat Jev's result as a lead, not proof. Do not edit code solely because Jev flagged it; follow the user's task instructions.

Avoid sending credentials, private keys, or unrelated sensitive data in state. The tool sends its state and questions to TypeSafe's API.
