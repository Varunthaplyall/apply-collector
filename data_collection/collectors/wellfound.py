"""
Wellfound (AngelList) collector — BLOCKED.

All approaches return 403 (Cloudflare):
  - GraphQL API at https://wellfound.com/graphql → 403
  - JSON sitemap at https://wellfound.com/jobs.json → 403
  - XML sitemap at https://wellfound.com/sitemap.xml → 403

To unblock, one would need:
  1. A real browser session with Playwright (Cloudflare JS challenge bypass)
  2. Or an API key / partnership with Wellfound

Last tested: 2026-06-16
"""

# This module is intentionally a no-op stub.
# Wellfound is documented in CLAUDE.md under "Dead / Blocked sources".
