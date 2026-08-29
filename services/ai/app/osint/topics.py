"""Topic taxonomy and keyword-based tagging for OSINT items.

Four tracked topics: china, taiwan, semiconductors, ai.
Tagging is deterministic keyword matching (no LLM call) so the feed
works even when the Anthropic API is unavailable or over budget.
"""

import re

# Topic slug -> display label
TOPICS = {
    "china": "China",
    "taiwan": "Taiwan",
    "semiconductors": "Semiconductors",
    "ai": "AI",
}

# Case-insensitive phrases matched on word boundaries.
_KEYWORDS_CI = {
    "china": [
        "china", "chinese", "beijing", "prc", "ccp", "xi jinping",
        "communist party", "pla", "people's liberation army", "hong kong",
        "shanghai", "shenzhen", "belt and road", "made in china",
        "state council", "mofcom", "cac", "miit", "yuan", "renminbi",
        "huawei", "smic", "alibaba", "tencent", "bytedance", "baidu",
        "deepseek", "zhipu", "moonshot",
    ],
    "taiwan": [
        "taiwan", "taiwanese", "taipei", "tsmc", "cross-strait",
        "taiwan strait", "kmt", "kuomintang", "dpp", "mediatek", "foxconn",
        "hon hai", "umc", "reunification", "one china",
    ],
    "semiconductors": [
        "semiconductor", "semiconductors", "chip", "chips", "chipmaker",
        "chipmaking", "foundry", "fab", "fabs", "wafer", "lithography",
        "euv", "duv", "node", "nanometer", "tsmc", "nvidia", "asml",
        "intel", "samsung", "micron", "sk hynix", "qualcomm", "arm",
        "gpu", "gpus", "hbm", "advanced packaging", "export controls",
        "export control", "chips act", "entity list", "bis",
        "smic", "gallium", "germanium", "rare earth", "rare earths",
    ],
    "ai": [
        "artificial intelligence", "machine learning", "deep learning",
        "large language model", "large language models", "llm", "llms",
        "generative ai", "frontier model", "frontier models", "openai",
        "anthropic", "deepmind", "chatgpt", "claude", "gemini", "gpt",
        "neural network", "ai safety", "ai policy", "ai regulation",
        "compute", "training run", "inference", "agentic", "chatbot",
        "deepseek", "superintelligence", "agi", "foundation model",
        "foundation models", "ai act",
    ],
}

# Case-sensitive tokens (short acronyms that are ambiguous lowercased).
_KEYWORDS_CS = {
    "ai": ["AI", "A.I."],
}


def _compile(phrases: list[str], flags: int) -> re.Pattern:
    escaped = sorted((re.escape(p) for p in phrases), key=len, reverse=True)
    return re.compile(r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)", flags)

_PATTERNS_CI = {t: _compile(p, re.IGNORECASE) for t, p in _KEYWORDS_CI.items()}
_PATTERNS_CS = {t: _compile(p, 0) for t, p in _KEYWORDS_CS.items()}


def tag_text(title: str, summary: str = "", default_topics: list[str] | None = None):
    """Tag an item with topic slugs and a relevance score.

    Title hits count 2, summary hits count 1 (capped at 3 per topic).
    Source default_topics are always included with a baseline score of 1.
    Returns (topics: list[str], relevance: int).
    """
    title = title or ""
    summary = summary or ""
    scores: dict[str, int] = {}

    for topic in TOPICS:
        score = 0
        for patterns in (_PATTERNS_CI, _PATTERNS_CS):
            pat = patterns.get(topic)
            if not pat:
                continue
            score += 2 * min(len(pat.findall(title)), 3)
            score += min(len(pat.findall(summary)), 3)
        if score:
            scores[topic] = min(score, 9)

    for topic in default_topics or []:
        if topic in TOPICS and topic not in scores:
            scores[topic] = 1

    topics = sorted(scores, key=lambda t: (-scores[t], t))
    return topics, sum(scores.values())
