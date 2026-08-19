"""
Input Guardrails
================
Guardrails are SAFETY CHECKS that run BEFORE any AI agent touches anything.

WHY DO WE NEED INPUT GUARDRAILS?
Without them, a user could ask the AI to test:
  - http://localhost:3000  (internal dev server — leaks internal info)
  - http://192.168.1.1    (router admin panel — dangerous)
  - http://competitor.com  (unauthorized testing — legal risk)
  - ftp://someserver.com   (wrong protocol)

This module validates the target URL BEFORE the discovery agent is even created.

HOW IT FITS IN THE PIPELINE:
  User provides URL → [InputGuardrail] → Discovery Agent → ...
"""

import re                    # Regular expressions for pattern matching
from urllib.parse import urlparse  # Standard library URL parser

from app.config.settings import settings  # Our settings with ALLOWED_TARGET_DOMAINS


class InputGuardrailError(Exception):
    """
    Custom exception raised when an input fails a guardrail check.

    Using a custom exception (instead of ValueError) makes it easy to catch
    ONLY guardrail failures in the validate_target_node without catching
    unrelated ValueErrors from other code.
    """
    pass


def validate_target_url(url: str) -> str:
    """
    Validates that the target URL is safe, properly formatted, and allowed.

    This function runs FIVE checks in order:
      1. URL format — must be parseable
      2. Scheme — must be http or https
      3. Host — must not be empty
      4. Private/loopback addresses — must not be internal
      5. Domain allowlist — must be in ALLOWED_TARGET_DOMAINS (if configured)

    Args:
        url: The raw URL string the user wants to test
             e.g. "https://example.com" or "http://myapp.staging.com/login"

    Returns:
        The validated URL string (normalized form)

    Raises:
        InputGuardrailError: If any of the 5 checks fail
    """

    # -------------------------------------------------------------------------
    # CHECK 1: URL Format
    # urlparse() splits a URL into its components without throwing exceptions
    # e.g. "https://example.com:8080/path?q=1#section" becomes:
    #   scheme="https", netloc="example.com:8080", path="/path", query="q=1"
    # -------------------------------------------------------------------------
    parsed = urlparse(url)

    # -------------------------------------------------------------------------
    # CHECK 2: Scheme (Protocol)
    # We only allow web protocols — not ftp://, file://, javascript://, etc.
    # -------------------------------------------------------------------------
    if parsed.scheme not in ("http", "https"):
        raise InputGuardrailError(
            f"Invalid URL scheme '{parsed.scheme}'. "
            f"Only 'http' and 'https' are allowed. URL: '{url}'"
        )

    # -------------------------------------------------------------------------
    # CHECK 3: Host Presence
    # A URL like "https://" has no netloc → the user forgot the domain
    # -------------------------------------------------------------------------
    if not parsed.netloc:
        raise InputGuardrailError(
            f"URL '{url}' has no valid domain/host. "
            f"Example of a valid URL: 'https://example.com'"
        )

    # -------------------------------------------------------------------------
    # CHECK 4: Blocked Hosts (Loopback + Private IP Ranges)
    # parsed.hostname strips the port from netloc:
    #   "example.com:8080" → "example.com"
    #   "127.0.0.1:3000"   → "127.0.0.1"
    # -------------------------------------------------------------------------
    hostname = parsed.hostname or ""  # hostname can be None if netloc is unusual

    # Exact match blocklist — these host names are always blocked
    blocked_exact = {
        "localhost",   # Loopback hostname
        "127.0.0.1",   # IPv4 loopback
        "0.0.0.0",     # Binds to all interfaces — should never be a target
        "::1",         # IPv6 loopback
    }

    if hostname in blocked_exact:
        raise InputGuardrailError(
            f"Testing localhost or loopback addresses is not allowed. "
            f"Got hostname: '{hostname}'"
        )

    # Pattern blocklist — these IP ranges are private networks
    # Regex patterns:
    #   10\.         → matches 10.x.x.x (Class A private)
    #   192\.168\.   → matches 192.168.x.x (Class C private, home routers)
    #   172\.(16-31) → matches 172.16.x.x to 172.31.x.x (Class B private)
    private_ip_patterns = [
        r"^10\.",                         # 10.0.0.0/8
        r"^192\.168\.",                   # 192.168.0.0/16
        r"^172\.(1[6-9]|2[0-9]|3[01])\.",  # 172.16.0.0/12
    ]

    for pattern in private_ip_patterns:
        # re.match() checks if the string STARTS WITH the pattern
        if re.match(pattern, hostname):
            raise InputGuardrailError(
                f"Testing private/internal IP addresses is not allowed. "
                f"Got hostname: '{hostname}'"
            )

    # -------------------------------------------------------------------------
    # CHECK 5: Domain Allowlist
    # If ALLOWED_TARGET_DOMAINS is set in .env, only those domains are permitted.
    # This is useful in enterprise deployments to restrict scope.
    #
    # Example .env: ALLOWED_TARGET_DOMAINS=mycompany.com,staging.mycompany.com
    # -------------------------------------------------------------------------
    allowed_domains_raw = settings.allowed_target_domains.strip()

    if allowed_domains_raw:
        # Parse the comma-separated domain list
        # "example.com, myapp.com" → ["example.com", "myapp.com"]
        allowed_domains = [
            d.strip()            # Remove whitespace from each domain
            for d in allowed_domains_raw.split(",")  # Split on commas
            if d.strip()         # Skip empty strings (from trailing commas)
        ]

        # Check if the hostname matches any allowed domain
        # We allow exact matches AND subdomain matches:
        #   allowed: "example.com"
        #   allowed: "sub.example.com" ← subdomain is also allowed
        #   blocked: "evil-example.com" ← different domain
        is_allowed = any(
            hostname == domain                    # Exact match
            or hostname.endswith(f".{domain}")   # Subdomain match
            for domain in allowed_domains
        )

        if not is_allowed:
            raise InputGuardrailError(
                f"Domain '{hostname}' is not in the configured allowlist. "
                f"Allowed domains: {allowed_domains}. "
                f"To add it, update ALLOWED_TARGET_DOMAINS in your .env file."
            )

    # All checks passed — return the original URL (urlparse doesn't modify it)
    return url
