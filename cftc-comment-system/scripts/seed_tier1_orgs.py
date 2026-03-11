"""Seed the database with Tier 1 organizations from the spec."""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import async_session_factory
from app.models.models import Tier1Organization, OrgCategory

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complete Tier 1 organization list from the spec
# ---------------------------------------------------------------------------

TIER1_ORGANIZATIONS = [
    # Law Firms
    {"name": "Sullivan & Cromwell", "category": OrgCategory.LAW_FIRM, "variations": ["Sullivan & Cromwell LLP", "S&C"]},
    {"name": "Davis Polk & Wardwell", "category": OrgCategory.LAW_FIRM, "variations": ["Davis Polk"]},
    {"name": "Cleary Gottlieb Steen & Hamilton", "category": OrgCategory.LAW_FIRM, "variations": ["Cleary Gottlieb", "CGSH"]},
    {"name": "Skadden Arps Slate Meagher & Flom", "category": OrgCategory.LAW_FIRM, "variations": ["Skadden", "Skadden Arps"]},
    {"name": "WilmerHale", "category": OrgCategory.LAW_FIRM, "variations": ["Wilmer Cutler Pickering Hale and Dorr", "Wilmer Hale"]},
    {"name": "Debevoise & Plimpton", "category": OrgCategory.LAW_FIRM, "variations": ["Debevoise"]},
    {"name": "Paul Hastings", "category": OrgCategory.LAW_FIRM, "variations": ["Paul Hastings LLP"]},
    {"name": "Latham & Watkins", "category": OrgCategory.LAW_FIRM, "variations": ["Latham"]},
    {"name": "Covington & Burling", "category": OrgCategory.LAW_FIRM, "variations": ["Covington"]},
    {"name": "Gibson Dunn & Crutcher", "category": OrgCategory.LAW_FIRM, "variations": ["Gibson Dunn"]},
    {"name": "Katten Muchin Rosenman", "category": OrgCategory.LAW_FIRM, "variations": ["Katten"]},
    {"name": "Mayer Brown", "category": OrgCategory.LAW_FIRM, "variations": ["Mayer Brown LLP"]},
    {"name": "Morrison & Foerster", "category": OrgCategory.LAW_FIRM, "variations": ["MoFo", "Morrison Foerster"]},
    {"name": "Akin Gump Strauss Hauer & Feld", "category": OrgCategory.LAW_FIRM, "variations": ["Akin Gump"]},
    {"name": "Arnold & Porter", "category": OrgCategory.LAW_FIRM, "variations": ["Arnold & Porter Kaye Scholer"]},
    {"name": "K&L Gates", "category": OrgCategory.LAW_FIRM, "variations": ["KL Gates"]},
    {"name": "Sidley Austin", "category": OrgCategory.LAW_FIRM, "variations": ["Sidley"]},
    {"name": "White & Case", "category": OrgCategory.LAW_FIRM, "variations": ["White and Case"]},
    {"name": "Kirkland & Ellis", "category": OrgCategory.LAW_FIRM, "variations": ["Kirkland"]},
    {"name": "Cooley LLP", "category": OrgCategory.LAW_FIRM, "variations": ["Cooley"]},
    {"name": "Fenwick & West", "category": OrgCategory.LAW_FIRM, "variations": ["Fenwick"]},
    {"name": "Perkins Coie", "category": OrgCategory.LAW_FIRM, "variations": ["Perkins Coie LLP"]},
    {"name": "O'Melveny & Myers", "category": OrgCategory.LAW_FIRM, "variations": ["O'Melveny"]},

    # Industry Associations
    {"name": "Futures Industry Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["FIA"]},
    {"name": "International Swaps and Derivatives Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["ISDA"]},
    {"name": "Blockchain Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Coin Center", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Better Markets", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Securities Industry and Financial Markets Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["SIFMA"]},
    {"name": "Managed Funds Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["MFA"]},
    {"name": "National Futures Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["NFA"]},
    {"name": "Alternative Investment Management Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["AIMA"]},
    {"name": "Investment Company Institute", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["ICI"]},
    {"name": "CFA Institute", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "American Bankers Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["ABA"]},
    {"name": "Bank Policy Institute", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["BPI"]},
    {"name": "Independent Community Bankers of America", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["ICBA"]},
    {"name": "Chamber of Digital Commerce", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Digital Asset Markets Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["DAMA"]},
    {"name": "Crypto Council for Innovation", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["CCI"]},
    {"name": "DeFi Education Fund", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Global Digital Finance", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["GDF"]},
    {"name": "American Gaming Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["AGA"]},
    {"name": "Fantasy Sports & Gaming Association", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["FSGA"]},
    {"name": "Americans for Financial Reform", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["AFR"]},
    {"name": "Public Citizen", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": []},
    {"name": "Consumer Federation of America", "category": OrgCategory.INDUSTRY_ASSOCIATION, "variations": ["CFA"]},

    # Exchanges/Platforms
    {"name": "CME Group", "category": OrgCategory.EXCHANGE, "variations": ["Chicago Mercantile Exchange", "CME"]},
    {"name": "Intercontinental Exchange", "category": OrgCategory.EXCHANGE, "variations": ["ICE"]},
    {"name": "Cboe Global Markets", "category": OrgCategory.EXCHANGE, "variations": ["Cboe", "CBOE"]},
    {"name": "Nasdaq", "category": OrgCategory.EXCHANGE, "variations": ["NASDAQ"]},
    {"name": "Coinbase", "category": OrgCategory.EXCHANGE, "variations": ["Coinbase Global", "Coinbase Inc"]},
    {"name": "Kraken", "category": OrgCategory.EXCHANGE, "variations": ["Payward", "Kraken Digital Asset Exchange"]},
    {"name": "Gemini", "category": OrgCategory.EXCHANGE, "variations": ["Gemini Trust Company"]},
    {"name": "Binance.US", "category": OrgCategory.EXCHANGE, "variations": ["BAM Trading Services", "Binance"]},
    {"name": "Circle", "category": OrgCategory.EXCHANGE, "variations": ["Circle Internet Financial"]},
    {"name": "Paxos", "category": OrgCategory.EXCHANGE, "variations": ["Paxos Trust Company"]},
    {"name": "Kalshi", "category": OrgCategory.EXCHANGE, "variations": ["Kalshi Inc"]},
    {"name": "PredictIt", "category": OrgCategory.EXCHANGE, "variations": ["Victoria University of Wellington"]},
    {"name": "Interactive Brokers", "category": OrgCategory.EXCHANGE, "variations": ["IBKR"]},
    {"name": "Robinhood", "category": OrgCategory.EXCHANGE, "variations": ["Robinhood Markets"]},
    {"name": "Charles Schwab", "category": OrgCategory.EXCHANGE, "variations": ["Schwab"]},
    {"name": "TD Ameritrade", "category": OrgCategory.EXCHANGE, "variations": []},
    {"name": "E*TRADE", "category": OrgCategory.EXCHANGE, "variations": ["ETRADE", "E-Trade"]},
    {"name": "Citadel Securities", "category": OrgCategory.EXCHANGE, "variations": ["Citadel"]},
    {"name": "Jane Street", "category": OrgCategory.EXCHANGE, "variations": ["Jane Street Capital"]},
    {"name": "Jump Trading", "category": OrgCategory.EXCHANGE, "variations": ["Jump Crypto"]},
    {"name": "Flow Traders", "category": OrgCategory.EXCHANGE, "variations": []},

    # Government Agencies
    {"name": "Securities and Exchange Commission", "category": OrgCategory.GOVERNMENT, "variations": ["SEC"]},
    {"name": "Federal Reserve Board", "category": OrgCategory.GOVERNMENT, "variations": ["Federal Reserve", "Fed", "Board of Governors"]},
    {"name": "FDIC", "category": OrgCategory.GOVERNMENT, "variations": ["Federal Deposit Insurance Corporation"]},
    {"name": "Office of the Comptroller of the Currency", "category": OrgCategory.GOVERNMENT, "variations": ["OCC"]},
    {"name": "Department of the Treasury", "category": OrgCategory.GOVERNMENT, "variations": ["Treasury", "U.S. Treasury"]},
    {"name": "FinCEN", "category": OrgCategory.GOVERNMENT, "variations": ["Financial Crimes Enforcement Network"]},
    {"name": "North American Securities Administrators Association", "category": OrgCategory.GOVERNMENT, "variations": ["NASAA"]},
    {"name": "Conference of State Bank Supervisors", "category": OrgCategory.GOVERNMENT, "variations": ["CSBS"]},

    # Academia/Think Tanks
    {"name": "Mercatus Center", "category": OrgCategory.ACADEMIA, "variations": ["Mercatus Center at George Mason University"]},
    {"name": "Brookings Institution", "category": OrgCategory.ACADEMIA, "variations": ["Brookings"]},
    {"name": "Roosevelt Institute", "category": OrgCategory.ACADEMIA, "variations": []},
    {"name": "Cato Institute", "category": OrgCategory.ACADEMIA, "variations": ["Cato"]},
]


async def seed_tier1_organizations():
    """Insert all Tier 1 organizations (skip duplicates)."""
    async with async_session_factory() as session:
        count = 0
        for org_data in TIER1_ORGANIZATIONS:
            stmt = pg_insert(Tier1Organization).values(
                name=org_data["name"],
                category=org_data["category"],
                name_variations=org_data.get("variations", []),
            ).on_conflict_do_nothing(index_elements=["name"])

            await session.execute(stmt)
            count += 1

        await session.commit()
        logger.info(f"Seeded {count} Tier 1 organizations")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_tier1_organizations())
