"""
iimjobs.com / Naukri collector — BLOCKED.

Status (tested 2026-06-16):
  - iimjobs.com: Now a Next.js SPA. /j/search-jobs returns HTML shell.
    Backend API at api.iimjobs.com requires auth (401). No public JSON
    endpoint found. Sitemap returns 404.

  - Naukri jobapi/v3/search: Returns 406 {"message":"recaptcha required"}.
    Even with full browser headers (sec-ch-ua, systemid, clientid),
    Naukri requires reCAPTCHA verification for all API calls.

To unblock either source:
  1. Browser automation with Playwright + stealth plugin (mimic real user)
  2. Or an API key / partnership

Last tested: 2026-06-16
"""

# This module is intentionally a no-op stub.
# Both sources are documented in CLAUDE.md under "Dead / Blocked sources".
