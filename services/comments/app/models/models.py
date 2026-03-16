"""Model constants for the CFTC Comment Analysis System (SQLite).

With the SQLite conversion, ORM models are no longer used.
This file provides string constants that match the DB schema values,
for use in services that need to reference tag types, categories, etc.
"""

# Tag types (stored as TEXT in comment_tags.tag_type)
TAG_TYPE_TOPIC = "TOPIC"
TAG_TYPE_LEGAL_CITATION = "LEGAL_CITATION"
TAG_TYPE_THEME = "THEME"

# Organization categories (stored as TEXT in tier1_organizations.category)
ORG_CATEGORY_LAW_FIRM = "LAW_FIRM"
ORG_CATEGORY_INDUSTRY_ASSOCIATION = "INDUSTRY_ASSOCIATION"
ORG_CATEGORY_EXCHANGE = "EXCHANGE"
ORG_CATEGORY_GOVERNMENT = "GOVERNMENT"
ORG_CATEGORY_ACADEMIA = "ACADEMIA"

# Sentiment values (stored as TEXT in comments.sentiment)
SENTIMENT_SUPPORT = "SUPPORT"
SENTIMENT_OPPOSE = "OPPOSE"
SENTIMENT_MIXED = "MIXED"
SENTIMENT_NEUTRAL = "NEUTRAL"

# Priority levels (stored as TEXT in proposed_rules.priority_level)
PRIORITY_HIGH = "HIGH"
PRIORITY_STANDARD = "STANDARD"

# Rule status (stored as TEXT in proposed_rules.status)
STATUS_OPEN = "OPEN"
STATUS_CLOSED = "CLOSED"
