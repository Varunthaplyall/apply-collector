"""
Slug discovery helper for Greenhouse and Lever APIs.
Automatically discovers valid ATS board slugs for given company names.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


def generate_slug_guesses(company_name: str) -> list[str]:
    """Generate common slug variants for a company name."""
    name = company_name.lower().strip()
    guesses = [
        name,
        name.replace(" ", ""),
        name.replace(" ", "-"),
        name.replace(" ", "_"),
    ]
    # first word only if multi-word
    if " " in name:
        guesses.append(name.split()[0])

    abbreviations = {
        "urban company": ["urbancompany", "urban-company", "urbanclap"],
        "cure.fit": ["curefit", "cure-fit", "cultfit", "cult-fit"],
        "phonepe": ["phonepe", "phone-pe"],
        "browserstack": ["browserstack", "browser-stack"],
        "clevertap": ["clevertap", "clever-tap"],
        "sharechat": ["sharechat", "share-chat"],
        "dream11": ["dream11", "dream-11"],
        "khatabook": ["khatabook", "khata-book"],
        "freshworks": ["freshworks", "freshworks-inc"],
    }
    if name in abbreviations:
        guesses.extend(abbreviations[name])

    return list(dict.fromkeys(guesses))  # dedup preserving order


async def check_greenhouse_slug(client: httpx.AsyncClient, slug: str) -> bool:
    """Check if a Greenhouse board slug is valid."""
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if "jobs" in data:
                return True
    except Exception:
        pass
    return False


async def check_lever_slug(client: httpx.AsyncClient, slug: str) -> bool:
    """Check if a Lever posting slug is valid."""
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                return True
    except Exception:
        pass
    return False


async def discover_slug(
    company_name: str,
    check_greenhouse: bool = True,
    check_lever: bool = True,
) -> dict:
    """
    Discover valid ATS slugs for a company.

    Returns dict with keys: company, greenhouse_slug, lever_slug, found
    """
    guesses = generate_slug_guesses(company_name)
    result = {
        "company": company_name,
        "greenhouse_slug": None,
        "lever_slug": None,
        "found": False,
    }

    async with httpx.AsyncClient() as client:
        if check_greenhouse:
            for slug in guesses:
                if await check_greenhouse_slug(client, slug):
                    result["greenhouse_slug"] = slug
                    result["found"] = True
                    logger.info("Greenhouse HIT: %s -> %s", company_name, slug)
                    break

        if check_lever:
            for slug in guesses:
                if await check_lever_slug(client, slug):
                    result["lever_slug"] = slug
                    result["found"] = True
                    logger.info("Lever HIT: %s -> %s", company_name, slug)
                    break

    if not result["found"]:
        logger.debug("No ATS found for: %s", company_name)

    return result



