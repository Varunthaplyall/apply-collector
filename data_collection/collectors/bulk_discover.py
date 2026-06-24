"""
Bulk slug discovery for Greenhouse and Lever APIs.
Takes a large list of company names and discovers valid ATS slugs.
Appends verified hits to target_companies.json.

Usage:
    python -m data_collection.collectors.bulk_discover
    python -m data_collection.collectors.bulk_discover --batch-size 50 --concurrency 10
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

import httpx

from data_collection.config import CONFIG_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Massive company list: Indian unicorns/startups, YC companies, known Greenhouse/Lever users,
# S&P 500 tech companies, global enterprises
COMPANIES_TO_TEST = [
    # === Indian Unicorns & Scale-ups ===
    "Razorpay", "Zerodha", "Urban Company", "UrbanClap", "Dunzo", "ShareChat",
    "Moj", "Unacademy", "upGrad", "Khatabook", "Spinny", "Rapido", "Innovaccer",
    "CleverTap", "Whatfix", "Darwinbox", "BrowserStack", "Chargebee", "Hasura",
    "Freshworks", "Zoho", "Licious", "Cars24", "Lenskart", "Nykaa", "BigBasket",
    "Delhivery", "Pine Labs", "MPL", "Games24x7", "Dream11", "CRED", "Meesho",
    "PhonePe", "Groww", "Postman", "Slice", "Zeta", "OfBusiness", "Meesho",
    "PhysicsWallah", "Purplle", "The Sleep Company", "boAt", "Noise",
    "CoinSwitch", "CoinDCX", "Polygon", "Matic", "WazirX", "GoTo",
    "Acko", "Digit Insurance", "PolicyBazaar", "Policybazaar", "Ola Electric",
    "Ola", "Swiggy", "Zomato", "Paytm", "Mobikwik", "FreeCharge",
    "Zerodha", "Groww", "Upstox", "Angel One", "Smallcase", "Jar",
    "Perfios", "Signzy", "Juspay", "Cashfree", "Razorpay",
    "Livspace", "NoBroker", "MagicBricks", "99acres", "Square Yards",
    "Vedantu", "Toppr", "Doubtnut", "Classplus", "Testbook",
    "CureFit", "CultFit", "Practo", "1mg", "PharmEasy", "MediBuddy",
    "DailyHunt", "InMobi", "mKhoj", "PhonePe",
    "Moglix", "IndustryBuying", "Udaan", "Jumbotail", "Bazaar",
    "BlackBuck", "Rivigo", "Delhivery", "Ecom Express",
    "Zenoti", "Capillary Technologies", "CleverTap", "MoEngage",
    "FreshToHome", "Licious", "Rebel Foods", "Faasos",
    "Unacademy", "Eruditus", "Scaler", "Newton School",
    "DeHaat", "Ninjacart", "WayCool", "Jumbotail",
    "Info Edge", "Naukri", "Zomato", "PolicyBazaar",

    # === Global SaaS / Enterprise ===
    "Zoom", "Atlassian", "Twilio", "Okta", "CrowdStrike", "Palo Alto Networks",
    "Fortinet", "Cloudflare", "Akamai", "Fastly",
    "MongoDB", "Elastic", "Confluent", "Databricks", "Snowflake",
    "HashiCorp", "Terraform", "Grafana Labs", "GitLab",
    "Notion", "Linear", "Airtable", "Monday.com", "Asana",
    "Figma", "Canva", "InVision", "Sketch",
    "Slack", "Discord", "ZoomInfo", "Salesloft", "Outreach",
    "HubSpot", "Zendesk", "Intercom", "Freshdesk",
    "Shopify", "BigCommerce", "Magento", "WooCommerce",
    "Stripe", "Square", "Adyen", "Checkout.com", "Plaid",
    "Plaid", "Plaid", "Brex", "Ramp", "Mercury",
    "Robinhood", "Coinbase", "Gemini", "Kraken", "Bitfinex",
    "Airbnb", "DoorDash", "Uber", "Lyft", "Instacart",
    "Netflix", "Spotify", "Reddit", "Pinterest", "Snap",
    "Pinterest", "Reddit", "Twitch", "YouTube", "Vimeo",
    "Dropbox", "Box", "Notion", "Evernote",
    "Vercel", "Netlify", "Cloudflare Pages", "Railway",
    "Render", "Fly.io", "Heroku", "DigitalOcean",
    "Supabase", "Firebase", "PlanetScale", "Neon",
    "Sentry", "New Relic", "Datadog", "PagerDuty",
    "CircleCI", "GitHub", "GitLab", "Bitbucket",
    "Docker", "Kubernetes", "Red Hat", "SUSE",
    "VMware", "Broadcom", "Nutanix", "Pure Storage",
    "Palantir", "C3.ai", "DataRobot", "H2O.ai",
    "OpenAI", "Anthropic", "DeepMind", "Cohere",
    "Perplexity", "You.com", "Character AI", "Midjourney",
    "Stability AI", "Hugging Face", "Weights & Biases",
    "Replicate", "Modal", "Together AI", "Fireworks AI",
    "Scale AI", "Labelbox", "Snorkel AI",
    "Confluent", "Databricks", "dbt Labs", "Fivetran",
    "Airbyte", "Hevo Data", "Census", "Hightouch",
    "LaunchDarkly", "Split.io", "Optimizely",
    "Calendly", "SavvyCal", "Cal.com",
    "1Password", "Dashlane", "Bitwarden",
    "Zapier", "Make", "Tray.io", "Workato",
    "Contentful", "Sanity", "Storyblok", "Strapi",
    "Algolia", "Typesense", "Meilisearch",
    "Segment", "mParticle", "Rudderstack",

    # === YC W24/S24/etc (recent batches) ===
    "Clerky", "Deel", "Rippling", "Gusto",
    "Webflow", "Framer", "Carrd",
    "Loom", "Tella", "Vidyard",
    "Grammarly", "Notion", "Coda",
    "Retool", "Appsmith", "Tooljet",
    "Temporal", "Inngest", "Trigger.dev",
    "Neon", "PlanetScale", "Turso",
    "Resend", "Loops", "Customer.io",
    "Knock", "Novu", "Courier",
    "Wiz", "Orca Security", "Lacework",
    "Ramp", "Brex", "Mercury",

    # === Indian Tech (Greenhouse/Lever) ===
    "Ola", "Ola Electric", "Swiggy", "Zomato", "Paytm",
    "PhonePe", "Razorpay", "CRED", "Meesho", "Groww",
    "Postman", "Freshworks", "BrowserStack", "Chargebee",
    "Hasura", "CleverTap", "Whatfix", "Darwinbox",
    "Innovaccer", "Zoho", "Zerodha",
    "ShareChat", "Unacademy", "Khatabook", "Spinny",
    "Rapido", "MPL", "Dream11", "Lenskart",
    "Nykaa", "BigBasket", "Delhivery", "Pine Labs",

    # === Global Enterprise (check if on Greenhouse/Lever) ===
    "Microsoft", "Google", "Amazon", "Apple", "Meta",
    "IBM", "Oracle", "SAP", "Salesforce", "Adobe",
    "Intel", "AMD", "Nvidia", "Qualcomm", "Broadcom",
    "Cisco", "Juniper", "Arista", "Palo Alto Networks",
    "Dell", "HP", "Lenovo", "Samsung",
    "Accenture", "Deloitte", "McKinsey", "BCG", "Bain",
    "Goldman Sachs", "JP Morgan", "Morgan Stanley",
    "Citadel", "Two Sigma", "Jane Street", "DE Shaw",
    "Jump Trading", "Hudson River Trading", "Tower Research",
    "Bloomberg", "Reuters", "FactSet",
    "Visa", "Mastercard", "AmEx",
    "Walmart Labs", "Target", "Costco", "Home Depot",
    "Tesla", "SpaceX", "Blue Origin", "Virgin Galactic",
    "Rivian", "Lucid Motors", "Nio", "BYD",
    "Palantir", "Anduril", "Shield AI", "Skydio",

    # === More Startups (high-growth) ===
    "Figma", "Notion", "Linear", "Vercel",
    "Supabase", "Neon", "Railway", "Render",
    "Retool", "Appsmith", "Tooljet", "Internal",
    "Loom", "Tella", "Descript",
    "Ramp", "Brex", "Mercury", "Arc",
    "Deel", "Remote", "Oyster", "Papaya Global",
    "Rippling", "Gusto", "Justworks",
    "Vanta", "Drata", "Sprinto", "Thoropass",
    "Wiz", "Orca Security", "Pentera",
    "Harness", "Harness", "Armory", "Codefresh",
    "LaunchDarkly", "Split", "Statsig",
    "Temporal", "Inngest", "Trigger.dev",
    "Resend", "Loops", "Knock", "Novu",
    "Clerky", "Stripe Atlas", "Clerky",
    "Metabase", "Lightdash", "Cube",
    "Grafana Labs", "Prometheus", "Thanos",
    "Dagster", "Airflow", "Prefect", "Mage",
    "LangChain", "LlamaIndex", "Pinecone", "Weaviate",
    "Chroma", "Qdrant", "Milvus",
    "BentoML", "Seldon", "Anyscale",
    "Gradio", "Streamlit", "Panel",
    "Weights & Biases", "Neptune.ai", "MLflow",
    "Anyscale", "Modal", "Replicate",
    "SkyPilot", "RunPod", "Lambda Labs",
    "PostHog", "Amplitude", "Mixpanel",
    "Sentry", "Bugsnag", "Rollbar",
    "Linear", "Shortcut", "Height",
    "Coda", "Slite", "Nuclino",
    "Slack", "Teams", "Zoom",
    "Calendly", "Cal.com", "SavvyCal",
    "Notion", "Confluence", "Coda",
    "Figma", "Miro", "FigJam",
    "Canva", "Adobe Express", "Visme",
    "Loom", "Vidyard", "Wistia",
    "Intercom", "Crisp", "Tidio",
    "Drift", "Qualified", "Gong",
    "Clari", "Revenue.io", "Outreach",
    "Salesloft", "Apollo", "ZoomInfo",
    "HubSpot", "Pipedrive", "Close",
    "Freshworks", "Zoho", "Insightly",
    "Xero", "QuickBooks", "FreshBooks",
    "Gusto", "Rippling", "Paychex",
    "Betterment", "Wealthfront", "SoFi",
    "Chime", "Current", "Dave",
    "Plaid", "MX", "Finicity",
    "Chainlink", "Uniswap", "Aave",
    "Compound", "MakerDAO", "Lido",
    "Solana", "Avalanche", "Polygon",
    "Arbitrum", "Optimism", "Base",
    "Phantom", "Backpack", "Rabby",
    "OpenSea", "Magic Eden", "Blur",
    "Dapper Labs", "Immutable", "Sorare",

    # === Consulting / IT services (India presence) ===
    "Infosys", "TCS", "Wipro", "HCL", "Tech Mahindra",
    "Cognizant", "Accenture", "Capgemini", "IBM",
    "LTIMindtree", "Mphasis", "L&T Technology",
    "Persistent Systems", "Zensar", "Hexaware",
    "Birlasoft", "NIIT Technologies", "KPIT",
    "Tata Elxsi", "Happiest Minds", "Cyient",
    "Sonata Software", "eClerx", "Mastek",

    # === Additional verified working (known Greenhouse users) ===
    "Acorns", "Affirm", "Airtable", "Algolia",
    "Amplitude", "AppLovin", "Arctic Wolf",
    "Attentive", "Auctane", "Automattic",
    "Axiom", "Benchling", "Birchbox",
    "Bitly", "Blend", "Block (Square)",
    "Bloomreach", "Bob", "Braze",
    "Calendly", "Carta", "Cerebras",
    "Checkr", "Chime", "Circle",
    "Cockroach Labs", "Collibra", "Compass",
    "Contentful", "Confluent", "Coupang",
    "Coursera", "Cruise", "D2iQ",
    "Dapper Labs", "Deel", "DoorDash",
    "Drata", "Drift", "Duo Security",
    "Dutchie", "Earnin", "Elastic",
    "Eventbrite", "Expel", "Extend",
    "Faire", "Fivetran", "Flexport",
    "G2", "GE Digital", "GitLab",
    "Glassdoor", "Glossier", "Gong",
    "Grammarly", "Greenlight", "Grubhub",
    "HashiCorp", "Heap", "Hinge",
    "Honey", "Honor", "Ibotta",
    "Impossible Foods", "Instabase", "Iterable",
    "Jamf", "JetBrains", "John Deere",
    "Karat", "Kforce", "Kong",
    "Kustomer", "Lattice", "LaunchDarkly",
    "Lemonade", "Lending Club", "Level",
    "Loom", "Loom", "Lucid",
    "Luma", "Lyra Health", "Marqeta",
    "MasterClass", "Medallia", "Miro",
    "MongoDB", "Navan", "Netlify",
    "Nextdoor", "Niantic", "Nuvemshop",
    "Nvidia", "Olo", "One Medical",
    "Palantir", "PandaDoc", "Patreon",
    "Pendo", "Plaid", "Planet Labs",
    "Postmates", "Procore", "Qualtrics",
    "Quizlet", "Ramp", "Redfin",
    "Retool", "Ripple", "Riskified",
    "Rivian", "Roku", "Rubrik",
    "Samsara", "Scopely", "Segment",
    "ServiceTitan", "Shippo", "Sift",
    "Snyk", "SoFi", "Sourcegraph",
    "Spotify", "Squarespace", "Stack Overflow",
    "StubHub", "Sumo Logic", "Sweetgreen",
    "Tanium", "TaskRabbit", "Tempus",
    "Toast", "Tonal", "TripActions",
    "Trulia", "TurboTax", "Twitch",
    "Unity", "Upwork", "UserTesting",
    "Vanta", "Vimeo", "Warby Parker",
    "Wayfair", "Webflow", "Wish",
    "Wiz", "Wrike", "Yelp",
    "Zapier", "Zenefits", "Zillow",
    "ZoomInfo", "Zscaler",

    # === Indian Startups (seed/series-A, added 2026-06-16) ===
    "Zepto", "Blinkit", "Navi", "Slice", "Open Financial", "Fi Money",
    "Jupiter", "KreditBee", "Lendingkart", "Setu", "Hyperface", "M2P Fintech",
    "Niyo", "Freo", "Karza", "Bureau", "Leegality", "Digio",
    "Smallcase", "Upstox", "Zerodha",

    # === Global YC/Startup slugs (added 2026-06-16) ===
    "Pilot", "Superhuman", "Coda", "Craft Ventures",
]


async def check_greenhouse(client, slug):
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


async def check_lever(client, slug):
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


def generate_slug_guesses(company_name):
    """Generate common slug variants for a company name."""
    name = company_name.lower().strip()
    guesses = [
        name,
        name.replace(" ", ""),
        name.replace(" ", "-"),
        name.replace(" ", "_"),
    ]
    if " " in name:
        guesses.append(name.split()[0])

    # Common known slug mappings
    known_slugs = {
        "anthropic": ["anthropic"],
        "databricks": ["databricks-1"],
        "stripe": ["stripe"],
        "figma": ["figma"],
        "notion": ["notion"],
        "airbnb": ["airbnb"],
        "okta": ["okta"],
        "brex": ["brex"],
        "coinbase": ["coinbase"],
        "twilio": ["twilio"],
        "shopify": ["shopify"],
        "reddit": ["reddit"],
        "discord": ["discord"],
        "dropbox": ["dropbox"],
        "doordash": ["doordash"],
        "lyft": ["lyft"],
        "instacart": ["instacart"],
        "robinhood": ["robinhood"],
        "pinterest": ["pinterest"],
        "asana": ["asana"],
        "mongodb": ["mongodb"],
        "datadog": ["datadog"],
        "cloudflare": ["cloudflare"],
        "elastic": ["elastic"],
        "grafana": ["grafana"],
        "sentry": ["sentry"],
        "vercel": ["vercel"],
        "netlify": ["netlify"],
        "gitlab": ["gitlab"],
        "postman": ["postman"],
        "circleci": ["circleci"],
        "workato": ["workato"],
        "contentful": ["contentful"],
        "sanity": ["sanity"],
        "calendly": ["calendly"],
        "hubspot": ["hubspot"],
        "intercom": ["intercom"],
        "freshworks": ["freshworks", "freshworks-inc"],
        "browserstack": ["browserstack", "browser-stack"],
        "chargebee": ["chargebee"],
        "clevertap": ["clevertap", "clever-tap"],
        "whatfix": ["whatfix"],
        "darwinbox": ["darwinbox"],
        "innovaccer": ["innovaccer"],
        "razorpay": ["razorpay"],
        "urban company": ["urbancompany", "urban-company", "urbanclap"],
        "sharechat": ["sharechat", "share-chat"],
        "khatabook": ["khatabook", "khata-book"],
        "dream11": ["dream11", "dream-11"],
        "hasura": ["hasura"],
        "zoho": ["zoho"],
        "zerodha": ["zerodha"],
        "delhivery": ["delhivery"],
        "pine labs": ["pinelabs", "pine-labs"],
        "mpl": ["mobile-premier-league", "mpl"],
        "nykaa": ["nykaa", "fsn-ecommerce"],
        "bigbasket": ["bigbasket", "big-basket"],
        "swiggy": ["swiggy"],
        "zomato": ["zomato"],
        "paytm": ["paytm", "one97-communications"],
        "phonepe": ["phonepe", "phone-pe"],
        "groww": ["groww"],
        "cred": ["cred"],
        "meesho": ["meesho"],
        "ola": ["ola", "ani-technologies"],
        "unacademy": ["unacademy"],
        "upgrad": ["upgrad"],
        "spinny": ["spinny"],
        "rapido": ["rapido"],
        "lenskart": ["lenskart"],
        "games24x7": ["games24x7", "games-24x7"],
        "deel": ["deel"],
        "rippling": ["rippling"],
        "gusto": ["gusto"],
        "ramp": ["ramp"],
        "wiz": ["wiz"],
        "temporal": ["temporal"],
        "resend": ["resend"],
        "neon": ["neon"],
        "supabase": ["supabase"],
        "modal": ["modal"],
        "replicate": ["replicate"],
        "perplexity": ["perplexity-ai", "perplexity"],
        "openai": ["openai"],
        "hugging face": ["huggingface"],
        "cohere": ["cohere"],
        "midjourney": ["midjourney"],
        "cruise": ["cruise"],
        "rivian": ["rivian"],
        "figma": ["figma"],
        "canva": ["canva"],
        "grammarly": ["grammarly"],
        "duolingo": ["duolingo"],
        "coursera": ["coursera"],
        "udemy": ["udemy"],

        # Indian startups (added 2026-06-16)
        "zepto": ["zepto", "zepto-ecommerce", "zeptonow"],
        "blinkit": ["blinkit", "grofers"],
        "navi": ["navi", "navi-technologies", "navi-finserv"],
        "slice": ["slice", "slice-fintech", "slicebank"],
        "open financial": ["open-financial", "open", "open-fin"],
        "fi money": ["fi-money", "fi", "epifi"],
        "jupiter": ["jupiter", "jupiter-money", "amica-financial"],
        "kreditbee": ["kreditbee", "kredit-bee", "finovation"],
        "lendingkart": ["lendingkart", "lending-kart"],
        "setu": ["setu", "setu-associates"],
        "hyperface": ["hyperface"],
        "m2p fintech": ["m2p-fintech", "m2p", "m2pfintech"],
        "niyo": ["niyo", "niyo-solutions", "niyosolutions"],
        "freo": ["freo", "freo-save", "moneytap"],
        "karza": ["karza", "karza-technologies"],
        "bureau": ["bureau", "bureau-id", "bureau-inc"],
        "leegality": ["leegality"],
        "digio": ["digio", "digio-in"],
        "smallcase": ["smallcase", "smallcase-technologies"],
        "upstox": ["upstox", "rksv"],
        "zerodha": ["zerodha"],

        # Global startups (added 2026-06-16)
        "pilot": ["pilot-com", "pilot"],
        "superhuman": ["superhuman", "superhuman-com"],
        "coda": ["coda-hq", "coda"],
        "craft ventures": ["craft", "craft-ventures"],
    }
    if name in known_slugs:
        guesses.extend(known_slugs[name])

    return list(dict.fromkeys(guesses))


async def discover_batch(companies, concurrency=10):
    """Discover slugs for a batch of companies."""
    semaphore = asyncio.Semaphore(concurrency)
    hits = {"greenhouse": {}, "lever": {}}

    async def _check_company(name):
        async with semaphore:
            guesses = generate_slug_guesses(name)
            async with httpx.AsyncClient() as client:
                for slug in guesses:
                    if await check_greenhouse(client, slug):
                        hits["greenhouse"][name] = slug
                        logger.info("  GH HIT: %s -> %s", name, slug)
                        break
                for slug in guesses:
                    if await check_lever(client, slug):
                        hits["lever"][name] = slug
                        logger.info("  LV HIT: %s -> %s", name, slug)
                        break

    # Rate limit: spread requests with batching
    batch_size = concurrency
    unique_companies = list(dict.fromkeys(companies))  # dedup preserving order
    logger.info("Testing %d unique companies ...", len(unique_companies))

    for i in range(0, len(unique_companies), batch_size):
        batch = unique_companies[i:i + batch_size]
        tasks = [_check_company(name) for name in batch]
        await asyncio.gather(*tasks)
        # Small delay between batches to be polite
        if i + batch_size < len(unique_companies):
            await asyncio.sleep(0.5)

    return hits


def load_existing_config():
    """Load existing target_companies.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


def merge_hits_into_config(config, hits):
    """Merge discovered slugs into config, avoiding duplicates."""
    existing_slugs = set()
    for c in config["companies"]:
        if c.get("slug"):
            existing_slugs.add(c["slug"])
        if c.get("tenant"):
            existing_slugs.add(c["tenant"])

    added = {"greenhouse": 0, "lever": 0}

    for name, slug in hits["greenhouse"].items():
        if slug not in existing_slugs:
            config["companies"].append({
                "name": name, "ats": "greenhouse", "slug": slug,
                "discovered": "bulk_discover",
            })
            existing_slugs.add(slug)
            added["greenhouse"] += 1

    for name, slug in hits["lever"].items():
        if slug not in existing_slugs:
            config["companies"].append({
                "name": name, "ats": "lever", "slug": slug,
                "discovered": "bulk_discover",
            })
            existing_slugs.add(slug)
            added["lever"] += 1

    return added


async def main():
    logger.info("=" * 60)
    logger.info("Bulk ATS Slug Discovery")
    logger.info("=" * 60)

    config = load_existing_config()
    existing_gh = sum(1 for c in config["companies"] if c.get("ats") == "greenhouse")
    existing_lever = sum(1 for c in config["companies"] if c.get("ats") == "lever")
    logger.info("Existing: %d Greenhouse, %d Lever", existing_gh, existing_lever)

    start = time.time()
    hits = await discover_batch(COMPANIES_TO_TEST, concurrency=10)
    elapsed = time.time() - start

    logger.info("Discovery complete in %.1fs", elapsed)
    logger.info("Found: %d Greenhouse hits, %d Lever hits",
                len(hits["greenhouse"]), len(hits["lever"]))

    added = merge_hits_into_config(config, hits)
    logger.info("Added: %d new Greenhouse, %d new Lever", added["greenhouse"], added["lever"])

    # Save updated config
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    logger.info("Updated %s", CONFIG_PATH)

    # Print summary
    new_gh = sum(1 for c in config["companies"] if c.get("ats") == "greenhouse")
    new_lever = sum(1 for c in config["companies"] if c.get("ats") == "lever")
    logger.info("Total now: %d Greenhouse, %d Lever", new_gh, new_lever)


if __name__ == "__main__":
    asyncio.run(main())
