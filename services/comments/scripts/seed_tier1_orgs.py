"""Seed the database with Tier 1 organizations from the spec (SQLite version)."""

import json
import logging

from app.core.database import get_connection
from app.core.schema import init_schema

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complete Tier 1 organization list from the spec
# ---------------------------------------------------------------------------

TIER1_ORGANIZATIONS = [
    # Law Firms
    {"name": "Sullivan & Cromwell", "category": "LAW_FIRM", "variations": ["Sullivan & Cromwell LLP", "S&C"]},
    {"name": "Davis Polk & Wardwell", "category": "LAW_FIRM", "variations": ["Davis Polk"]},
    {"name": "Cleary Gottlieb Steen & Hamilton", "category": "LAW_FIRM", "variations": ["Cleary Gottlieb", "CGSH"]},
    {"name": "Skadden Arps Slate Meagher & Flom", "category": "LAW_FIRM", "variations": ["Skadden", "Skadden Arps"]},
    {"name": "WilmerHale", "category": "LAW_FIRM", "variations": ["Wilmer Cutler Pickering Hale and Dorr", "Wilmer Hale"]},
    {"name": "Debevoise & Plimpton", "category": "LAW_FIRM", "variations": ["Debevoise"]},
    {"name": "Paul Hastings", "category": "LAW_FIRM", "variations": ["Paul Hastings LLP"]},
    {"name": "Latham & Watkins", "category": "LAW_FIRM", "variations": ["Latham"]},
    {"name": "Covington & Burling", "category": "LAW_FIRM", "variations": ["Covington"]},
    {"name": "Gibson Dunn & Crutcher", "category": "LAW_FIRM", "variations": ["Gibson Dunn"]},
    {"name": "Katten Muchin Rosenman", "category": "LAW_FIRM", "variations": ["Katten"]},
    {"name": "Mayer Brown", "category": "LAW_FIRM", "variations": ["Mayer Brown LLP"]},
    {"name": "Morrison & Foerster", "category": "LAW_FIRM", "variations": ["MoFo", "Morrison Foerster"]},
    {"name": "Akin Gump Strauss Hauer & Feld", "category": "LAW_FIRM", "variations": ["Akin Gump"]},
    {"name": "Arnold & Porter", "category": "LAW_FIRM", "variations": ["Arnold & Porter Kaye Scholer"]},
    {"name": "K&L Gates", "category": "LAW_FIRM", "variations": ["KL Gates"]},
    {"name": "Sidley Austin", "category": "LAW_FIRM", "variations": ["Sidley"]},
    {"name": "White & Case", "category": "LAW_FIRM", "variations": ["White and Case"]},
    {"name": "Kirkland & Ellis", "category": "LAW_FIRM", "variations": ["Kirkland"]},
    {"name": "Cooley LLP", "category": "LAW_FIRM", "variations": ["Cooley"]},
    {"name": "Fenwick & West", "category": "LAW_FIRM", "variations": ["Fenwick"]},
    {"name": "Perkins Coie", "category": "LAW_FIRM", "variations": ["Perkins Coie LLP"]},
    {"name": "O'Melveny & Myers", "category": "LAW_FIRM", "variations": ["O'Melveny"]},

    # Industry Associations
    {"name": "Futures Industry Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["FIA"]},
    {"name": "International Swaps and Derivatives Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["ISDA"]},
    {"name": "Blockchain Association", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Coin Center", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Better Markets", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Securities Industry and Financial Markets Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["SIFMA"]},
    {"name": "Managed Funds Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["MFA"]},
    {"name": "National Futures Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["NFA"]},
    {"name": "Alternative Investment Management Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["AIMA"]},
    {"name": "Investment Company Institute", "category": "INDUSTRY_ASSOCIATION", "variations": ["ICI"]},
    {"name": "CFA Institute", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "American Bankers Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["ABA"]},
    {"name": "Bank Policy Institute", "category": "INDUSTRY_ASSOCIATION", "variations": ["BPI"]},
    {"name": "Independent Community Bankers of America", "category": "INDUSTRY_ASSOCIATION", "variations": ["ICBA"]},
    {"name": "Chamber of Digital Commerce", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Digital Asset Markets Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["DAMA"]},
    {"name": "Crypto Council for Innovation", "category": "INDUSTRY_ASSOCIATION", "variations": ["CCI"]},
    {"name": "DeFi Education Fund", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Global Digital Finance", "category": "INDUSTRY_ASSOCIATION", "variations": ["GDF"]},
    {"name": "American Gaming Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["AGA"]},
    {"name": "Fantasy Sports & Gaming Association", "category": "INDUSTRY_ASSOCIATION", "variations": ["FSGA"]},
    {"name": "Americans for Financial Reform", "category": "INDUSTRY_ASSOCIATION", "variations": ["AFR"]},
    {"name": "Public Citizen", "category": "INDUSTRY_ASSOCIATION", "variations": []},
    {"name": "Consumer Federation of America", "category": "INDUSTRY_ASSOCIATION", "variations": ["CFA"]},

    # Exchanges/Platforms
    {"name": "CME Group", "category": "EXCHANGE", "variations": ["Chicago Mercantile Exchange", "CME"]},
    {"name": "Intercontinental Exchange", "category": "EXCHANGE", "variations": ["ICE"]},
    {"name": "Cboe Global Markets", "category": "EXCHANGE", "variations": ["Cboe", "CBOE"]},
    {"name": "Nasdaq", "category": "EXCHANGE", "variations": ["NASDAQ"]},
    {"name": "Coinbase", "category": "EXCHANGE", "variations": ["Coinbase Global", "Coinbase Inc"]},
    {"name": "Kraken", "category": "EXCHANGE", "variations": ["Payward", "Kraken Digital Asset Exchange"]},
    {"name": "Gemini", "category": "EXCHANGE", "variations": ["Gemini Trust Company"]},
    {"name": "Binance.US", "category": "EXCHANGE", "variations": ["BAM Trading Services", "Binance"]},
    {"name": "Circle", "category": "EXCHANGE", "variations": ["Circle Internet Financial"]},
    {"name": "Paxos", "category": "EXCHANGE", "variations": ["Paxos Trust Company"]},
    {"name": "Kalshi", "category": "EXCHANGE", "variations": ["Kalshi Inc"]},
    {"name": "PredictIt", "category": "EXCHANGE", "variations": ["Victoria University of Wellington"]},
    {"name": "Interactive Brokers", "category": "EXCHANGE", "variations": ["IBKR"]},
    {"name": "Robinhood", "category": "EXCHANGE", "variations": ["Robinhood Markets"]},
    {"name": "Charles Schwab", "category": "EXCHANGE", "variations": ["Schwab"]},
    {"name": "TD Ameritrade", "category": "EXCHANGE", "variations": []},
    {"name": "E*TRADE", "category": "EXCHANGE", "variations": ["ETRADE", "E-Trade"]},
    {"name": "Citadel Securities", "category": "EXCHANGE", "variations": ["Citadel"]},
    {"name": "Jane Street", "category": "EXCHANGE", "variations": ["Jane Street Capital"]},
    {"name": "Jump Trading", "category": "EXCHANGE", "variations": ["Jump Crypto"]},
    {"name": "Flow Traders", "category": "EXCHANGE", "variations": []},

    # Government Agencies
    {"name": "Securities and Exchange Commission", "category": "GOVERNMENT", "variations": ["SEC"]},
    {"name": "Federal Reserve Board", "category": "GOVERNMENT", "variations": ["Federal Reserve", "Fed", "Board of Governors"]},
    {"name": "FDIC", "category": "GOVERNMENT", "variations": ["Federal Deposit Insurance Corporation"]},
    {"name": "Office of the Comptroller of the Currency", "category": "GOVERNMENT", "variations": ["OCC"]},
    {"name": "Department of the Treasury", "category": "GOVERNMENT", "variations": ["Treasury", "U.S. Treasury"]},
    {"name": "FinCEN", "category": "GOVERNMENT", "variations": ["Financial Crimes Enforcement Network"]},
    {"name": "North American Securities Administrators Association", "category": "GOVERNMENT", "variations": ["NASAA"]},
    {"name": "Conference of State Bank Supervisors", "category": "GOVERNMENT", "variations": ["CSBS"]},

    # Academia/Think Tanks
    {"name": "Mercatus Center", "category": "ACADEMIA", "variations": ["Mercatus Center at George Mason University"]},
    {"name": "Brookings Institution", "category": "ACADEMIA", "variations": ["Brookings"]},
    {"name": "Roosevelt Institute", "category": "ACADEMIA", "variations": []},
    {"name": "Cato Institute", "category": "ACADEMIA", "variations": ["Cato"]},
]


def seed_tier1_organizations():
    """Insert all Tier 1 organizations (skip duplicates)."""
    conn = get_connection()
    try:
        init_schema(conn)
        count = 0
        for org_data in TIER1_ORGANIZATIONS:
            existing = conn.execute(
                "SELECT id FROM tier1_organizations WHERE name = ?",
                (org_data["name"],)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO tier1_organizations (name, category, name_variations) VALUES (?, ?, ?)",
                (org_data["name"], org_data["category"], json.dumps(org_data.get("variations", [])))
            )
            count += 1
        conn.commit()
        logger.info(f"Seeded {count} Tier 1 organizations")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_tier1_organizations()
