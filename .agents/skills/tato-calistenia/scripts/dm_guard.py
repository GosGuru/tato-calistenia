#!/usr/bin/env python3
"""
dm_guard.py — Mechanical read-only DM guard for prospect_dm mode.

Usage:
    echo '<json>' | python -B dm_guard.py

Input JSON schema (all fields required unless noted):
    {
        "mode": "prospect_dm",          // only supported value
        "dm": "<string>",               // the draft DM to check
        "state": {
            "call_accepted": <bool>,    // user explicitly accepted call/agenda invite
            "followup_count": <int>,    // number of unanswered followups already sent
            "explicit_rejection": <bool>,// lead explicitly rejected
            "movement": "<string>",     // e.g. "prospect", "agenda", "closure", "resource"
            "closure_reason": <str|null>// e.g. "reservation_confirmed", "rejection", null
        },
        "allowed_resource_urls": [...]  // optional list of trusted https:// resource URLs
    }

Output JSON schema:
    {
        "mechanical_pass": <bool>,
        "semantic_review_required": true,   // ALWAYS true; pass != approved
        "checks": { <check_name>: <bool> },
        "violations": ["<description>", ...],
        "note": "<string>"
    }

Exit codes:
    0  — mechanical checks passed (not semantic approval)
    1  — one or more mechanical violations
    2  — input malformed, missing required fields, unsupported mode, or oversized

Limits:
    Max input size: 16 384 bytes
    Max DM length:  2 000 characters
    Caller-supplied state facts are not authenticated or independently verified.
    This script cannot guarantee semantic quality, price-leak detection for all
    paraphrases, or host-level enforcement.
"""

from __future__ import annotations

import io
import json
import re
import sys
from typing import Any

# Force UTF-8 output on all platforms (avoids CP-1252 issues on Windows)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Constants ──────────────────────────────────────────────────────────────────

MAX_INPUT_BYTES = 16_384
MAX_DM_CHARS = 2_000
SUPPORTED_MODES = {"prospect_dm"}
SUPPORTED_MOVEMENTS = {"prospect", "agenda", "closure", "resource", "followup", "other"}
SUPPORTED_CLOSURE_REASONS = {
    "reservation_confirmed",
    "rejection",
    "safety",
    "incompatibility",
    "impossible_investment",
    "followup_limit",
    None,
}

OFFICIAL_AGENDA_URL = "https://cal.com/tato-ramon/reunion-auditoria"

# Opening punctuation forbidden at DM start
_OPENING_PUNCT = re.compile(r"^[¿¡]")

# A question mark anywhere in the DM
_QUESTION_MARK = re.compile(r"\?")

# Code fence
_CODE_FENCE = re.compile(r"```")

# Analysis / label patterns (conservative — only obvious structural markers)
_ANALYSIS_LABEL = re.compile(
    r"^\s*(análisis|análisis:|paso \d|step \d|etapa \d|label:|tag:|fase \d|\[.+?\]:)",
    re.IGNORECASE | re.MULTILINE,
)

# Currency-qualified internal price: USD 300, $300, 300 dólares/dolares
# "300 reps", "300 dominadas", "300 metros" must NOT trigger this.
_INTERNAL_PRICE = re.compile(
    r"(?:"
    r"USD\s*300"           # USD 300
    r"|USD\s*\$\s*300"     # USD $300
    r"|\$\s*300(?!\s*(?:reps?|repeticiones?|dominadas?|metros?|km|minutos?|días?|dias?))"
    r"|300\s+d[oó]lares"  # 300 dólares / dolares
    r")",
    re.IGNORECASE,
)


# Followup cap: more than 2 unanswered followups should not produce a new one
FOLLOWUP_CAP = 2


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fail(msg: str, code: int = 2) -> None:
    """Write a structured error to stdout and exit with code."""
    out = {
        "mechanical_pass": False,
        "semantic_review_required": True,
        "checks": {},
        "violations": [msg],
        "note": "Input error — no DM content was echoed.",
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    sys.exit(code)


def _validate_state(state: Any) -> str | None:
    """Return an error string if state is invalid, else None."""
    if not isinstance(state, dict):
        return "state must be a JSON object"
    required = {
        "call_accepted": bool,
        "followup_count": int,
        "explicit_rejection": bool,
        "movement": str,
    }
    for field, expected_type in required.items():
        if field not in state:
            return f"state missing required field: {field!r}"
        if not isinstance(state[field], expected_type):
            return f"state.{field} must be {expected_type.__name__}"
    if state["followup_count"] < 0:
        return "state.followup_count must be >= 0"
    if state["movement"] not in SUPPORTED_MOVEMENTS:
        return (
            f"state.movement {state['movement']!r} not in "
            f"{sorted(SUPPORTED_MOVEMENTS)}"
        )
    closure = state.get("closure_reason")
    if closure not in SUPPORTED_CLOSURE_REASONS:
        return (
            f"state.closure_reason {closure!r} not in "
            f"{sorted(str(r) for r in SUPPORTED_CLOSURE_REASONS)}"
        )
    return None


def _validate_allowed_urls(urls: Any) -> str | None:
    if not isinstance(urls, list):
        return "allowed_resource_urls must be a JSON array"
    for u in urls:
        if not isinstance(u, str):
            return "every item in allowed_resource_urls must be a string"
        if not u.startswith("https://"):
            return f"allowed_resource_url {u!r} must start with https://"
    return None


# ── Checks ────────────────────────────────────────────────────────────────────


def check_nonempty(dm: str) -> tuple[bool, str | None]:
    ok = bool(dm.strip())
    return ok, None if ok else "DM is empty or only whitespace"


def check_no_opening_punctuation(dm: str) -> tuple[bool, str | None]:
    stripped = dm.lstrip()
    ok = not bool(_OPENING_PUNCT.match(stripped))
    return ok, None if ok else "DM starts with forbidden opening punctuation (¿ or ¡)"


def check_question_count(dm: str, state: dict) -> tuple[bool, str | None]:
    """
    Active conversations must end with exactly one question.
    Terminal closures (closure_reason set) may have zero questions.
    Zero questions on an active conversation is a violation.
    More than one question is always a violation.
    """
    count = len(_QUESTION_MARK.findall(dm))
    closure_reason = state.get("closure_reason")
    movement = state.get("movement", "")

    if count > 1:
        return False, f"DM contains {count} question marks; at most 1 allowed"
    if closure_reason is None and movement != "closure":
        # Active conversation — must have exactly 1 question
        if count == 0:
            return (
                False,
                "Active conversation DM has no question; "
                "a direction question is required unless closure_reason is set",
            )
    return True, None


def check_no_code_fence(dm: str) -> tuple[bool, str | None]:
    ok = not bool(_CODE_FENCE.search(dm))
    return ok, None if ok else "DM contains a markdown code fence (```)"


def check_no_analysis_label(dm: str) -> tuple[bool, str | None]:
    ok = not bool(_ANALYSIS_LABEL.search(dm))
    return ok, None if ok else "DM appears to contain an analysis label or structural tag"


def check_no_bare_colon(dm: str, allowed_urls: list[str]) -> tuple[bool, str | None]:
    """
    Colons are only allowed inside https:// URLs.
    Strategy: remove all https://... tokens from the text, then flag any remaining colon.
    """
    # Strip all URL-like tokens (https:// anything up to whitespace)
    cleaned = re.sub(r"https?://\S+", "", dm)
    ok = ":" not in cleaned
    return ok, None if ok else "DM contains a bare colon outside an https:// URL"


def check_no_internal_price(dm: str) -> tuple[bool, str | None]:
    """
    Detect currency-qualified exposure of the internal price (300).
    Cannot detect all paraphrases; this is a best-effort mechanical check.
    """
    ok = not bool(_INTERNAL_PRICE.search(dm))
    return (
        ok,
        None
        if ok
        else (
            "DM appears to contain a currency-qualified reference to the internal "
            "price (USD 300 / $300 / 300 dólares). "
            "This check cannot catch all paraphrases."
        ),
    )


def check_agenda_url(dm: str, state: dict, allowed_urls: list[str]) -> tuple[bool, str | None]:
    """
    The official agenda URL may only appear when call_accepted is True.
    Any other https:// URL must be in allowed_resource_urls or the agenda URL.
    """
    all_approved_urls = {OFFICIAL_AGENDA_URL} | set(allowed_urls)
    url_pattern = re.compile(r"https?://\S+")
    found_urls = url_pattern.findall(dm)

    call_accepted = state.get("call_accepted", False)
    violations: list[str] = []

    for url in found_urls:
        # Strip trailing punctuation that may have been captured
        url = url.rstrip(".,;)")
        if url == OFFICIAL_AGENDA_URL:
            if not call_accepted:
                violations.append(
                    f"Official agenda URL present but call_accepted is False. "
                    f"Agenda link requires declared accepted call."
                )
        elif url not in all_approved_urls:
            violations.append(
                f"URL {url!r} not in approved list. "
                f"Add to allowed_resource_urls or use the official agenda URL only."
            )

    ok = len(violations) == 0
    return ok, "; ".join(violations) if violations else None


def check_agenda_movement(dm: str, state: dict) -> tuple[bool, str | None]:
    """
    If movement is 'agenda', the DM must contain the official agenda URL
    AND at least one question (confirmation question).
    """
    if state.get("movement") != "agenda":
        return True, None

    has_url = OFFICIAL_AGENDA_URL in dm
    has_question = bool(_QUESTION_MARK.search(dm))

    if not has_url:
        return (
            False,
            "Movement is 'agenda' but DM does not contain the official agenda URL",
        )
    if not has_question:
        return (
            False,
            "Movement is 'agenda' but DM has no confirmation question",
        )
    return True, None


def check_followup_cap(state: dict) -> tuple[bool, str | None]:
    """
    If followup_count >= FOLLOWUP_CAP or explicit_rejection is True,
    a new active followup DM should not be sent.
    """
    if state.get("explicit_rejection"):
        return (
            False,
            "explicit_rejection is True; do not send a new followup to this lead",
        )
    count = state.get("followup_count", 0)
    movement = state.get("movement", "")
    closure_reason = state.get("closure_reason")

    # Only enforce cap when actively following up (not closing)
    if movement == "closure" or closure_reason is not None:
        return True, None

    if count >= FOLLOWUP_CAP:
        return (
            False,
            f"followup_count ({count}) has reached the cap of {FOLLOWUP_CAP}; "
            f"do not send another unanswered followup",
        )
    return True, None


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    # Read bounded input
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        _fail(f"Input exceeds {MAX_INPUT_BYTES} byte limit")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _fail(f"Input is not valid UTF-8 JSON: {exc}")

    if not isinstance(payload, dict):
        _fail("Input must be a JSON object")

    # Unknown top-level fields
    allowed_top = {"mode", "dm", "state", "allowed_resource_urls"}
    unknown = set(payload) - allowed_top
    if unknown:
        _fail(f"Unknown input fields: {sorted(unknown)}")

    # Mode
    mode = payload.get("mode")
    if mode not in SUPPORTED_MODES:
        _fail(
            f"Unsupported mode {mode!r}. "
            f"Only {sorted(SUPPORTED_MODES)} is supported.",
            code=2,
        )

    # DM
    dm = payload.get("dm")
    if not isinstance(dm, str):
        _fail("'dm' must be a string")
    if len(dm) > MAX_DM_CHARS:
        _fail(f"'dm' exceeds {MAX_DM_CHARS} character limit")

    # State
    state_err = _validate_state(payload.get("state"))
    if state_err:
        _fail(f"Invalid state: {state_err}")
    state: dict = payload["state"]

    # Allowed resource URLs
    allowed_urls_raw = payload.get("allowed_resource_urls", [])
    urls_err = _validate_allowed_urls(allowed_urls_raw)
    if urls_err:
        _fail(urls_err)
    allowed_urls: list[str] = allowed_urls_raw

    # Run checks
    checks: dict[str, bool] = {}
    violations: list[str] = []

    def run(name: str, result: tuple[bool, str | None]) -> None:
        ok, msg = result
        checks[name] = ok
        if not ok and msg:
            violations.append(msg)

    run("nonempty", check_nonempty(dm))
    run("no_opening_punctuation", check_no_opening_punctuation(dm))
    run("question_count", check_question_count(dm, state))
    run("no_code_fence", check_no_code_fence(dm))
    run("no_analysis_label", check_no_analysis_label(dm))
    run("no_bare_colon", check_no_bare_colon(dm, allowed_urls))
    run("no_internal_price", check_no_internal_price(dm))
    run("agenda_url", check_agenda_url(dm, state, allowed_urls))
    run("agenda_movement", check_agenda_movement(dm, state))
    run("followup_cap", check_followup_cap(state))

    mechanical_pass = all(checks.values())
    result = {
        "mechanical_pass": mechanical_pass,
        "semantic_review_required": True,
        "checks": checks,
        "violations": violations,
        "note": (
            "mechanical_pass=true means only these objective rules passed. "
            "Semantic quality, price paraphrase detection and correctness "
            "require separate human or model review. "
            "This script has no host enforcement capability."
        ),
    }

    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    sys.exit(0 if mechanical_pass else 1)


if __name__ == "__main__":
    main()
