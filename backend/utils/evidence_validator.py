"""Physical Evidence Validator — verifies findings against actual source code.

Each finding from an agent cites a line number and CWE. This validator
reads the actual code at that line and checks if the vulnerability pattern
truly exists. If the evidence doesn't match, the finding is discarded.

This is the single highest-impact filter for false positives:
agents often hallucinate line numbers and CWE references.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
#  Vulnerability signature patterns
#  Maps CWE → regex patterns that MUST match
#  the cited line of code for the finding to be
#  considered valid.
# ──────────────────────────────────────────────

CWE_PATTERNS: dict[str, list[str]] = {
    # SQL injection (CWE-89)
    "CWE-89": [
        r"execute\s*\(", r"cursor\.", r"raw_input", r"f\s*['\"]",
        r"\{\s*[^}]+\}", r"%\s*\(?\w+\)?", r"format\s*\(", r"\+.*WHERE",
        r"SELECT.*\+", r"query.*\{", r"\.execute\(.*f['\"]",
    ],
    # OS Command Injection (CWE-78)
    "CWE-78": [
        r"os\.system", r"subprocess\.", r"shell\s*=\s*True",
        r"eval\s*\(", r"exec\s*\(", r"Popen", r"`.*`",
    ],
    # Cross-site Scripting (CWE-79)
    "CWE-79": [
        r"\.innerHTML", r"\.outerHTML", r"document\.write",
        r"\.html\s*\(", r"\.append\s*\(", r"response\.write",
        r"<script>", r"unsafe-inline", r"dangerouslySetInnerHTML",
        r"render_template_string", r"\{\{.*\}\}",
    ],
    # Hardcoded Credentials (CWE-798 / CWE-259)
    "CWE-798": [
        r"=", r"password", r"secret", r"key", r"token", r"credential",
        r"auth", r"api_key", r"api", r"sk-", r"AKIA", r"-----BEGIN",
    ],
    "CWE-259": [
        r"=", r"password", r"passwd", r"pwd", r"secret",
    ],
    # Path Traversal (CWE-22)
    "CWE-22": [
        r"open\s*\(", r"\.\./", r"file\s*=", r"path\s*=",
        r"os\.path\.join", r"send_file", r"get\s*\(\s*[\"']",
        r"zipfile", r"extractall", r"symlink",
    ],
    # Insecure Deserialization (CWE-502)
    "CWE-502": [
        r"pickle\.loads", r"yaml\.load\s*\(", r"eval\s*\(",
        r"jsonpickle", r"marshal\.load", r"__reduce__",
    ],
    # Missing CSRF Protection (no CWE standard, use heuristics)
    "csrf": [
        r"@app\.route", r"def\s+\w+", r"request\.", r"POST",
        r"form", r"transfer", r"delete", r"session",
    ],
    # Information Exposure (CWE-200)
    "CWE-200": [
        r"debug\s*=\s*True", r"print\s*\(", r"logger\.", r"stack",
        r"traceback", r"error", r"exception",
    ],
    # Hardcoded JWT / Crypto keys (CWE-321)
    "CWE-321": [
        r"secret", r"jwt", r"crypto", r"signing", r"private",
        r"-----BEGIN", r"key\s*=", r"token",
    ],
}

# CWE aliases — some agents use short codes
CWE_ALIASES: dict[str, list[str]] = {
    "89": ["CWE-89"],
    "78": ["CWE-78"],
    "79": ["CWE-79", "CWE-80"],
    "22": ["CWE-22"],
    "502": ["CWE-502"],
    "798": ["CWE-798", "CWE-259"],
    "259": ["CWE-259", "CWE-798"],
    "200": ["CWE-200"],
    "321": ["CWE-321"],
    "116": ["CWE-116"],
    "404": ["CWE-404"],
    "770": ["CWE-770"],
    "640": ["CWE-640"],
    "843": ["CWE-843"],
    "693": ["CWE-693"],
    "1173": ["CWE-1173"],
    "547": ["CWE-547"],
}


def extract_line_number(text: str) -> int | None:
    """Extract a line number from finding text.

    Handles formats: 'line 5', 'L5', 'line 5-7', 'line 5, 10'
    """
    # Try "line 5" or "Line 5" first
    m = re.search(r'(?:line|Line|LINE)\s+#?(\d+)', text)
    if m:
        return int(m.group(1))
    # Try "L5"
    m = re.search(r'\bL(\d+)\b', text)
    if m:
        return int(m.group(1))
    # Try "line:5"
    m = re.search(r'line[:\s]*(\d+)', text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def extract_code_lines(code: str) -> list[str]:
    """Split code into lines (1-indexed)."""
    return code.split("\n")


def extract_cwe(text: str) -> list[str]:
    """Extract CWE identifiers from text."""
    found: list[str] = []
    # Direct CWE references
    for m in re.finditer(r'CWE-(\d+)', text, re.IGNORECASE):
        cwe_num = m.group(1)
        found.extend(CWE_ALIASES.get(cwe_num, [f"CWE-{cwe_num}"]))
    # Common keywords without CWE prefix
    keywords = {
        "sql injection": ["CWE-89"],
        "sqli": ["CWE-89"],
        "command injection": ["CWE-78"],
        "cmd injection": ["CWE-78"],
        "xss": ["CWE-79"],
        "cross.site": ["CWE-79"],
        "hardcoded password": ["CWE-259", "CWE-798"],
        "hardcoded secret": ["CWE-798"],
        "path traversal": ["CWE-22"],
        "deserialization": ["CWE-502"],
        "pickle": ["CWE-502"],
        "csrf": ["csrf"],
    }
    lower = text.lower()
    for keyword, cwes in keywords.items():
        if keyword in lower:
            found.extend(cwes)
    return list(set(found))


def validate_finding(
    title: str,
    detail: str,
    code: str,
) -> dict[str, Any]:
    """Validate a single finding against the actual source code.

    Parameters
    ----------
    title : str
        Finding title.
    detail : str
        Finding detail/evidence text.
    code : str
        Original source code being reviewed.

    Returns
    -------
    dict with keys:
        valid (bool): True if evidence matches code
        reason (str): Why it was accepted/rejected
        line_number (int | None): Extracted line number
        cwes (list[str]): Extracted CWE references
        matched_patterns (list[str]): Which patterns matched
    """
    result: dict[str, Any] = {
        "valid": False,
        "reason": "",
        "line_number": None,
        "cwes": [],
        "matched_patterns": [],
    }

    # 1. Extract line number
    combined = f"{title}\n{detail}"
    line_num = extract_line_number(combined)
    result["line_number"] = line_num

    if line_num is None:
        result["reason"] = "No line number cited — cannot verify"
        return result

    # 2. Get code at that line (and ±1 for LLM off-by-one)
    code_lines = extract_code_lines(code)
    if line_num < 1 or line_num > len(code_lines):
        result["reason"] = f"Line {line_num} out of range (file has {len(code_lines)} lines)"
        return result

    # Check the cited line AND adjacent lines (±1) for evidence
    start = max(0, line_num - 2)  # 0-indexed, -1 for the line above
    end = min(len(code_lines), line_num + 1)  # +1 for the line below
    context_lines = code_lines[start:end]
    all_lines_text = "\n".join(context_lines)

    # 3. Extract CWE from finding
    cwes = extract_cwe(combined)
    result["cwes"] = cwes
    if not cwes:
        # No specific CWE — check if any context line has suspicious content
        suspicious = [
            r"os\.system", r"subprocess", r"eval\s*\(", r"exec\s*\(",
            r"pickle", r"sqlite3", r"execute\s*\(", r"request\.",
            r"open\s*\(", r"\.\./", r"password\s*=", r"secret\s*=",
        ]
        for pat in suspicious:
            if re.search(pat, all_lines_text):
                result["matched_patterns"].append(f"suspicious:{pat}")
                break
        if result["matched_patterns"]:
            result["valid"] = True
            result["reason"] = f"Lines {start+1}-{end} contain suspicious pattern (no specific CWE)"
        else:
            result["reason"] = f"No CWE referenced and line {line_num} area is clean: {code_lines[line_num-1].strip()[:60]}"
        return result

    # 4. Check patterns for each CWE
    for cwe in cwes:
        patterns = CWE_PATTERNS.get(cwe, [])
        if not patterns:
            # Unknown CWE — soft accept if line has any code
            actual_line = code_lines[line_num - 1] if line_num <= len(code_lines) else ""
            if actual_line.strip():
                result["matched_patterns"].append(f"unknown_cwe:{cwe}")
                result["valid"] = True
                result["reason"] = f"Unknown CWE {cwe} but line {line_num} has code"
            else:
                result["reason"] = f"Unknown CWE {cwe} and line {line_num} is empty"
            continue

        # Check each pattern against context lines (±1)
        line_matches = []
        for pattern in patterns:
            if re.search(pattern, all_lines_text, re.IGNORECASE):
                line_matches.append(pattern)

        if line_matches:
            result["matched_patterns"].extend([f"{cwe}:{p}" for p in line_matches])
            result["valid"] = True
            result["reason"] = (
                f"Lines {start+1}-{end} match {cwe}: "
                f"{', '.join(line_matches[:3])}"
            )
        else:
            # No pattern matched — this is likely a hallucination
            result["reason"] = (
                f"Lines {start+1}-{end} have no {cwe} patterns: "
                f"'{code_lines[line_num-1].strip()[:60]}'"
            )

    return result


def batch_validate(
    findings: list[Any],
    code: str,
) -> tuple[list[Any], list[tuple[Any, str]]]:
    """Validate a batch of findings against source code.

    Returns
    -------
    tuple of (valid_findings, rejected_findings_with_reason)
    """
    valid = []
    rejected = []

    for finding in findings:
        title = getattr(finding, "title", "") or ""
        detail = getattr(finding, "detail", "") or ""

        result = validate_finding(title, detail, code)

        if result["valid"]:
            valid.append(finding)
        else:
            rejected.append((finding, result["reason"]))
            logger.debug(
                "Evidence rejected: [%s] %s — %s",
                getattr(finding, "agent", "?"),
                title[:50],
                result["reason"],
            )

    if rejected:
        logger.info(
            "Evidence validator: %d/%d findings accepted (%.0f%% kept)",
            len(valid),
            len(valid) + len(rejected),
            (len(valid) / max(len(valid) + len(rejected), 1)) * 100,
        )

    return valid, rejected
