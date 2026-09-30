"""Control mecánico optativo. Solo STDIN/STDOUT; nunca autoriza un envío."""

import json
import re
import sys

MAX_BYTES = 16384
MAX_TEXT = 4096
AGENDA = "https://cal.com/tato-ramon/reunion-auditoria"
TERMINAL = {
    "minor",
    "rejection",
    "investment_impossible",
    "incompatibility",
    "safety",
    "followup_limit",
    "booking_confirmed",
}
FIELDS = {"version", "text", "closure", "call_accepted"}
# Reconocimiento sintáctico limitado, no clasificación de intención comercial.
LINK = re.compile(r"(?:[a-z]+://|www\.)\S+|\b[\w-]+(?:\.[\w-]+)+/\S*", re.I)
PRICE = re.compile(
    r"(?<![\w\d])(?:USD|US\$|\$|dólares|dolares)\s*300(?!\d)"
    r"|(?<![\d.,])\b300(?:[.,]00)?\s*(?:USD\b|US\$|\$|dólares\b|dolares\b)",
    re.I,
)


def result(code, findings):
    status = {
        0: "mechanical_pass",
        1: "mechanical_findings",
        2: "invalid_input",
        3: "manual_review",
    }[code]
    return code, {
        "status": status,
        "findings": findings,
        "semantic_review_required": True,
        "enforcement": "manual_shadow",
    }


def evaluate(data):
    if (
        type(data) is not dict
        or set(data) != FIELDS
        or type(data["version"]) is not int
        or data["version"] != 1
        or type(data["text"]) is not str
        or not 1 <= len(data["text"]) <= MAX_TEXT
        or not data["text"].strip()
        or type(data["closure"]) is not str
        or data["closure"] not in TERMINAL | {"active"}
        or type(data["call_accepted"]) is not bool
    ):
        return result(2, ["schema_invalid"])
    text = data["text"]
    # Controles no imprimibles y Unicode no representable quedan fuera del alcance.
    if any(
        (ord(c) < 32 and c not in "\n\r\t") or 0xD800 <= ord(c) <= 0xDFFF for c in text
    ):
        return result(3, ["unsupported_text"])
    findings = []
    manual = []
    questions = text.count("?")
    if questions > 1:
        findings.append("multiple_question_marks")
    if data["closure"] == "active":
        if questions != 1 or not text.rstrip().endswith("?"):
            findings.append("active_final_question_required")
    elif questions:
        findings.append("terminal_question_forbidden")
    if "¿" in text or "¡" in text:
        findings.append("opening_punctuation")
    if "```" in text or "~~~" in text:
        findings.append("code_fence")
    remainder = text
    for match in LINK.finditer(text):
        link = match.group()
        if "cal.com" in link.lower():
            if link != AGENDA:
                findings.append("agenda_not_exact")
            else:
                line_start = text.rfind("\n", 0, match.start()) + 1
                line_end = text.find("\n", match.end())
                line = text[line_start : line_end if line_end != -1 else len(text)]
                if line.rstrip("\r") != AGENDA:
                    findings.append("agenda_not_standalone")
                if not data["call_accepted"]:
                    findings.append("agenda_acceptance_required")
                if data["closure"] != "active":
                    manual.append("agenda_in_terminal_context")
        else:
            manual.append("unsupported_resource")
        # Otro recurso no introduce una excepción nueva a la política de dos puntos.
        remainder = remainder.replace(link, "")
    if ":" in remainder:
        findings.append("colon_in_prose")
    if PRICE.search(text):
        findings.append("currency_qualified_300")
    if findings:
        return result(1, sorted(set(findings + manual)))
    if manual:
        return result(3, sorted(set(manual)))
    return result(0, [])


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate")
        obj[key] = value
    return obj


def reject_constant(_):
    raise ValueError("constant")


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("size")
        data = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        code, output = evaluate(data)
    except (ValueError, RecursionError, OSError):
        code, output = result(2, ["input_invalid"])
    print(json.dumps(output, ensure_ascii=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
