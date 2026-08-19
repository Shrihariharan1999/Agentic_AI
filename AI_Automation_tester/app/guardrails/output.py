"""
Output Guardrails
=================
Output guardrails validate and sanitize what AI agents PRODUCE before
it is stored in the database or returned to users.

WHY DO WE NEED OUTPUT GUARDRAILS?
AI agents process web pages that may contain:
  - Login form values (passwords accidentally captured in screenshots)
  - API keys in JavaScript
  - Credit card numbers in cart pages
  - Personally Identifiable Information (PII)

If these appear in the agent's output text and get stored, that's a data leak.
Output guardrails scan agent responses and REDACT sensitive patterns.

HOW IT FITS IN THE PIPELINE:
  ExecutorAgent produces "PASS: I filled the form with password=secret123" →
  [OutputGuardrail sanitizes] →
  "PASS: I filled the form with password=[REDACTED_PASSWORD]"
"""

import re   # Regular expressions for pattern-based text scanning


# -------------------------------------------------------------------------
# SENSITIVE DATA PATTERNS
# Each entry is a tuple: (regex_pattern, replacement_string)
# The regex matches the sensitive data, which gets replaced with the label.
#
# Pattern explanations:
#   r"password['\"]?\s*[:=]\s*['\"]?[\w@#$%^&*]+"
#     └─ matches: password="secret", password: abc123, password='p@ss!'
#   r"api.?key['\"]?\s*[:=]\s*['\"]?[\w\-]+"
#     └─ matches: api_key="sk-abc", apiKey: "xyz-123"
#   r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b"
#     └─ matches credit cards: 4111 1111 1111 1111, 4111-1111-1111-1111
# -------------------------------------------------------------------------
SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    # Passwords in key=value format
    (
        r"password['\"]?\s*[:=]\s*['\"]?[\w@#$%^&*!]+",
        "[REDACTED_PASSWORD]",
    ),
    # API keys and tokens
    (
        r"api[_\-]?key['\"]?\s*[:=]\s*['\"]?[\w\-]+",
        "[REDACTED_API_KEY]",
    ),
    # Secret values
    (
        r"secret['\"]?\s*[:=]\s*['\"]?[\w\-]+",
        "[REDACTED_SECRET]",
    ),
    # Authorization tokens (Bearer headers)
    (
        r"bearer\s+[A-Za-z0-9\-_\.]+",
        "Bearer [REDACTED_TOKEN]",
    ),
    # 16-digit credit card numbers (with optional spaces or dashes)
    (
        r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
        "[REDACTED_CARD_NUMBER]",
    ),
    # Social Security Numbers (US format: XXX-XX-XXXX)
    (
        r"\b\d{3}[\s\-]\d{2}[\s\-]\d{4}\b",
        "[REDACTED_SSN]",
    ),
]


def sanitize_output(text: str) -> str:
    """
    Scans agent-generated text for sensitive data and replaces it.

    This uses regex substitution — for each sensitive pattern,
    it finds all occurrences and replaces them with a labeled placeholder.

    Args:
        text: Raw text output from an AI agent (could be quite long)

    Returns:
        Sanitized text with sensitive data replaced by [REDACTED_...] labels
    """

    sanitized = text  # Start with the original text

    # Apply each pattern one by one
    for pattern, replacement in SENSITIVE_PATTERNS:
        # re.sub() replaces ALL matches of `pattern` in `sanitized` with `replacement`
        # re.IGNORECASE means "PASSWORD=..." and "password=..." both match
        sanitized = re.sub(
            pattern,       # The regex pattern to search for
            replacement,   # What to replace it with
            sanitized,     # The string to search in
            flags=re.IGNORECASE,  # Case-insensitive matching
        )

    return sanitized  # Return the cleaned text


def validate_non_empty(text: str, field_name: str) -> str:
    """
    Validates that an agent's output is not empty.

    Args:
        text: The output string to validate
        field_name: Name of the field (for error messages)

    Returns:
        The original text if it's non-empty

    Raises:
        ValueError: If the output is empty or whitespace-only
    """

    # Strip whitespace and check if anything remains
    if not text or not text.strip():
        raise ValueError(
            f"Agent produced empty output for field: '{field_name}'. "
            f"This usually means the LLM returned an empty response."
        )

    return text  # Return original (we don't strip — preserve formatting)
