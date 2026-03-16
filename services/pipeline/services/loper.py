"""
Loper Bright Vulnerability Analyzer — service layer.

Read-only queries against cftc_regulatory.db for Stage 1 scores,
Stage 2 assessments, challenge history, and CEA provisions.
"""

import json
import logging

logger = logging.getLogger(__name__)

# ── Allowed sort fields ──────────────────────────────────────────────

RULE_SORT_FIELDS = {
    "composite_score", "dim1_composite", "dim2_composite", "dim3_composite",
    "dim4_composite", "dim5_composite", "legal_challenge_subcomposite",
    "policy_priority_subcomposite", "publication_date", "title",
    "fr_citation", "action_category", "comment_multiplier",
}

GUIDANCE_SORT_FIELDS = {
    "composite_score", "g1_composite", "g2_composite", "g3_composite",
    "g4_composite", "g5_composite", "legal_challenge_subcomposite",
    "policy_priority_subcomposite", "publication_date", "title",
    "action_category", "document_type",
}

# ── Helpers ───────────────────────────────────────────────────────────

def _parse_json_field(val):
    """Safely parse a JSON string field, returning [] on failure."""
    if not val:
        return []
    try:
        return json.loads(val)
    except (json.JSONDecodeError, TypeError):
        return []


def _get_s2_for_citations(conn, citations):
    """Batch-fetch Stage 2 assessments for a list of FR citations.

    Returns dict[fr_citation] -> list[dict].
    """
    if not citations:
        return {}
    placeholders = ",".join("?" for _ in citations)
    rows = conn.execute(
        f"""SELECT id, fr_citation, module, stage1_score_triggering,
                   sonnet_validation_result, sonnet_validation_notes,
                   sonnet_revised_score, opus_analysis_run,
                   vulnerability_rating, confidence_level,
                   strongest_challenge_argument, strongest_defense_argument,
                   recommended_action, analyzed_at
            FROM stage2_assessments
            WHERE fr_citation IN ({placeholders})
            ORDER BY fr_citation, module""",
        citations,
    ).fetchall()

    result = {}
    for r in rows:
        d = dict(r)
        result.setdefault(d["fr_citation"], []).append(d)
    return result


def _s2_summary(s2_list):
    """Compute summary stats from a list of S2 assessment dicts."""
    if not s2_list:
        return {"modules_activated": 0, "modules_confirmed": 0,
                "confirmed_modules": [], "has_opus": False}
    confirmed = [a for a in s2_list
                 if a.get("sonnet_validation_result") in ("confirmed", "upgraded")]
    return {
        "modules_activated": len(s2_list),
        "modules_confirmed": len(confirmed),
        "confirmed_modules": [a["module"] for a in confirmed],
        "has_opus": any(a.get("opus_analysis_run") for a in s2_list),
    }


# ── Rules ─────────────────────────────────────────────────────────────

def list_rules(conn, *, action_category=None, vulnerability=None,
               min_score=None, max_score=None, search=None,
               has_challenge=None, has_dissent=None, validation=None,
               date_from=None, date_to=None,
               sort="composite_score", order="desc",
               page=1, page_size=50):
    """Paginated, filtered, sorted rules list with S2 data merged."""

    # Sanitize sort
    if sort not in RULE_SORT_FIELDS:
        sort = "composite_score"
    if order not in ("asc", "desc"):
        order = "desc"

    conditions = []
    params = []

    if action_category:
        conditions.append("s.action_category = ?")
        params.append(action_category)

    if vulnerability:
        conditions.append("s.legal_theory_tags LIKE ?")
        params.append(f"%{vulnerability}%")

    if min_score is not None:
        conditions.append("s.composite_score >= ?")
        params.append(float(min_score))

    if max_score is not None:
        conditions.append("s.composite_score <= ?")
        params.append(float(max_score))

    if search:
        conditions.append(
            "(s.title LIKE ? OR s.fr_citation LIKE ? OR s.docket_number LIKE ?)"
        )
        term = f"%{search}%"
        params.extend([term, term, term])

    if has_dissent is not None and has_dissent:
        conditions.append("s.has_commissioner_dissent = 1")

    if date_from:
        conditions.append("s.publication_date >= ?")
        params.append(date_from)

    if date_to:
        conditions.append("s.publication_date <= ?")
        params.append(date_to)

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Count total
    count_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM stage1_scores s {where}", params
    ).fetchone()
    total = count_row["cnt"]

    # Fetch page
    offset = (max(1, int(page)) - 1) * int(page_size)
    rows = conn.execute(
        f"""SELECT s.*,
                   d.voting_record, d.commissioner_statements_urls
            FROM stage1_scores s
            LEFT JOIN documents d ON s.fr_citation = d.fr_citation
            {where}
            ORDER BY s.{sort} {order} NULLS LAST
            LIMIT ? OFFSET ?""",
        params + [int(page_size), offset],
    ).fetchall()

    items = [dict(r) for r in rows]

    # Parse JSON fields
    for item in items:
        item["legal_theory_tags"] = _parse_json_field(item.get("legal_theory_tags"))
        item["cfr_sections"] = _parse_json_field(item.get("cfr_sections"))
        item["primary_statutory_authority"] = _parse_json_field(
            item.get("primary_statutory_authority")
        )

    # Merge S2 data
    citations = [item["fr_citation"] for item in items]
    s2_map = _get_s2_for_citations(conn, citations)
    for item in items:
        s2_list = s2_map.get(item["fr_citation"], [])
        item["s2_assessments"] = s2_list
        item["s2_summary"] = _s2_summary(s2_list)

    # Post-filter by validation if requested
    if validation:
        if validation == "confirmed":
            items = [i for i in items if i["s2_summary"]["modules_confirmed"] > 0]
            total = len(items)  # approximate; would need subquery for exact
        elif validation == "none":
            items = [i for i in items if i["s2_summary"]["modules_activated"] == 0]
            total = len(items)

    # Post-filter challenge history
    if has_challenge is not None and has_challenge:
        challenge_citations = set(
            r["fr_citation"] for r in conn.execute(
                "SELECT DISTINCT fr_citation FROM stage1_challenge_history WHERE fr_citation IS NOT NULL"
            ).fetchall()
        )
        items = [i for i in items if i["fr_citation"] in challenge_citations]
        total = len(items)

    return items, total


def get_rule_detail(conn, fr_citation):
    """Full rule detail with S2, challenges, CEA provisions, related rules."""

    # Core rule
    rule = conn.execute(
        """SELECT s.*, d.voting_record, d.commissioner_statements_urls,
                  d.full_text_length, d.url, d.description,
                  d.comment_period_end, d.regulations_dot_gov_comments,
                  d.related_proposed_rule, d.related_final_rule
           FROM stage1_scores s
           LEFT JOIN documents d ON s.fr_citation = d.fr_citation
           WHERE s.fr_citation = ?""",
        (fr_citation,),
    ).fetchone()

    if not rule:
        return None

    rule_dict = dict(rule)
    rule_dict["legal_theory_tags"] = _parse_json_field(rule_dict.get("legal_theory_tags"))
    rule_dict["cfr_sections"] = _parse_json_field(rule_dict.get("cfr_sections"))
    rule_dict["primary_statutory_authority"] = _parse_json_field(
        rule_dict.get("primary_statutory_authority")
    )

    # S2 assessments
    s2_rows = conn.execute(
        """SELECT * FROM stage2_assessments
           WHERE fr_citation = ?
           ORDER BY module""",
        (fr_citation,),
    ).fetchall()
    s2_assessments = [dict(r) for r in s2_rows]

    # Challenge history
    challenges = [dict(r) for r in conn.execute(
        """SELECT * FROM stage1_challenge_history
           WHERE fr_citation = ?
           ORDER BY date_decided DESC""",
        (fr_citation,),
    ).fetchall()]

    # CEA provisions
    cea_sections = rule_dict.get("primary_statutory_authority", [])
    cea_provisions = []
    if cea_sections:
        for sec in cea_sections:
            prov = conn.execute(
                "SELECT * FROM cea_provisions WHERE cea_section = ?",
                (sec,),
            ).fetchone()
            if prov:
                cea_provisions.append(dict(prov))

    # Related rules (same CEA provisions, exclude self)
    related_rules = []
    if cea_sections and len(cea_sections) > 0:
        like_clause = " OR ".join(
            "s.primary_statutory_authority LIKE ?" for _ in cea_sections[:3]
        )
        like_params = [f"%{sec}%" for sec in cea_sections[:3]]
        related = conn.execute(
            f"""SELECT s.fr_citation, s.title, s.composite_score,
                       s.action_category, s.dim1_composite
                FROM stage1_scores s
                WHERE ({like_clause}) AND s.fr_citation != ?
                ORDER BY s.composite_score DESC
                LIMIT 10""",
            like_params + [fr_citation],
        ).fetchall()
        related_rules = [dict(r) for r in related]

    # Related guidance
    related_guidance = []
    try:
        guidance_rows = conn.execute(
            """SELECT doc_id, title, composite_score, action_category,
                      document_type, g1_composite, g4_composite
               FROM stage1_guidance_scores
               WHERE parent_rule_citations LIKE ?
               ORDER BY composite_score DESC
               LIMIT 10""",
            (f"%{fr_citation}%",),
        ).fetchall()
        related_guidance = [dict(r) for r in guidance_rows]
    except Exception:
        pass  # Table may not have parent_rule_citations column

    return {
        "rule": rule_dict,
        "s2_assessments": s2_assessments,
        "challenges": challenges,
        "cea_provisions": cea_provisions,
        "related_rules": related_rules,
        "related_guidance": related_guidance,
    }


# ── Guidance ──────────────────────────────────────────────────────────

def list_guidance(conn, *, action_category=None, document_type=None,
                  division=None, min_score=None, max_score=None,
                  min_binding=None, vulnerability=None, search=None,
                  sort="composite_score", order="desc",
                  page=1, page_size=50):
    """Paginated, filtered, sorted guidance list."""

    if sort not in GUIDANCE_SORT_FIELDS:
        sort = "composite_score"
    if order not in ("asc", "desc"):
        order = "desc"

    conditions = []
    params = []

    if action_category:
        conditions.append("g.action_category = ?")
        params.append(action_category)

    if document_type:
        conditions.append("g.document_type = ?")
        params.append(document_type)

    if division:
        conditions.append("g.division = ?")
        params.append(division)

    if min_score is not None:
        conditions.append("g.composite_score >= ?")
        params.append(float(min_score))

    if max_score is not None:
        conditions.append("g.composite_score <= ?")
        params.append(float(max_score))

    if min_binding is not None:
        conditions.append("g.g4_composite >= ?")
        params.append(float(min_binding))

    if vulnerability:
        conditions.append("g.legal_theory_tags LIKE ?")
        params.append(f"%{vulnerability}%")

    if search:
        conditions.append("(g.title LIKE ? OR g.letter_number LIKE ?)")
        term = f"%{search}%"
        params.extend([term, term])

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    count_row = conn.execute(
        f"SELECT COUNT(*) as cnt FROM stage1_guidance_scores g {where}", params
    ).fetchone()
    total = count_row["cnt"]

    offset = (max(1, int(page)) - 1) * int(page_size)
    rows = conn.execute(
        f"""SELECT g.*
            FROM stage1_guidance_scores g
            {where}
            ORDER BY g.{sort} {order} NULLS LAST
            LIMIT ? OFFSET ?""",
        params + [int(page_size), offset],
    ).fetchall()

    items = [dict(r) for r in rows]
    for item in items:
        item["legal_theory_tags"] = _parse_json_field(item.get("legal_theory_tags"))
        item["mapped_cea_sections"] = _parse_json_field(item.get("mapped_cea_sections"))
        item["parent_rule_citations"] = _parse_json_field(
            item.get("parent_rule_citations")
        )

    return items, total


def get_guidance_detail(conn, doc_id):
    """Full guidance detail with parent rule cross-references."""

    guidance = conn.execute(
        """SELECT g.*, d.url, d.description, d.full_text_length
           FROM stage1_guidance_scores g
           LEFT JOIN documents d ON g.doc_id = d.id
           WHERE g.doc_id = ?""",
        (doc_id,),
    ).fetchone()

    if not guidance:
        return None

    g_dict = dict(guidance)
    g_dict["legal_theory_tags"] = _parse_json_field(g_dict.get("legal_theory_tags"))
    g_dict["mapped_cea_sections"] = _parse_json_field(g_dict.get("mapped_cea_sections"))
    parent_citations = _parse_json_field(g_dict.get("parent_rule_citations"))
    g_dict["parent_rule_citations"] = parent_citations

    # Parent rules
    parent_rules = []
    for citation in parent_citations[:5]:
        r = conn.execute(
            """SELECT fr_citation, title, composite_score, action_category
               FROM stage1_scores WHERE fr_citation = ?""",
            (citation,),
        ).fetchone()
        if r:
            parent_rules.append(dict(r))

    # Related guidance (same division + document_type)
    related = conn.execute(
        """SELECT doc_id, title, composite_score, action_category,
                  document_type, letter_number
           FROM stage1_guidance_scores
           WHERE division = ? AND document_type = ? AND doc_id != ?
           ORDER BY composite_score DESC
           LIMIT 10""",
        (g_dict.get("division"), g_dict.get("document_type"), doc_id),
    ).fetchall()

    return {
        "guidance": g_dict,
        "parent_rules": parent_rules,
        "related_guidance": [dict(r) for r in related],
    }


# ── Dashboard ─────────────────────────────────────────────────────────

def get_dashboard_stats(conn):
    """Aggregated stats for the dashboard view."""

    # Rule counts by action
    rule_actions = conn.execute(
        """SELECT action_category, COUNT(*) as cnt
           FROM stage1_scores
           GROUP BY action_category
           ORDER BY cnt DESC"""
    ).fetchall()

    # Guidance counts by action
    guidance_actions = conn.execute(
        """SELECT action_category, COUNT(*) as cnt
           FROM stage1_guidance_scores
           GROUP BY action_category
           ORDER BY cnt DESC"""
    ).fetchall()

    # Total counts
    rule_total = sum(r["cnt"] for r in rule_actions)
    guidance_total = sum(r["cnt"] for r in guidance_actions)

    # S2 validation summary
    s2_stats = conn.execute(
        """SELECT sonnet_validation_result, COUNT(*) as cnt
           FROM stage2_assessments
           GROUP BY sonnet_validation_result"""
    ).fetchall()
    s2_map = {r["sonnet_validation_result"]: r["cnt"] for r in s2_stats}

    # Active challenges
    active_challenges = conn.execute(
        """SELECT COUNT(*) as cnt FROM stage1_challenge_history
           WHERE current_status IN ('pending', 'good_law')"""
    ).fetchone()["cnt"]

    # Dimension averages
    dim_avgs = conn.execute(
        """SELECT
             AVG(dim1_composite) as avg_d1,
             AVG(dim2_composite) as avg_d2,
             AVG(dim3_composite) as avg_d3,
             AVG(dim4_composite) as avg_d4,
             AVG(dim5_composite) as avg_d5,
             AVG(composite_score) as avg_composite
           FROM stage1_scores"""
    ).fetchone()

    return {
        "rules_total": rule_total,
        "guidance_total": guidance_total,
        "rule_actions": [dict(r) for r in rule_actions],
        "guidance_actions": [dict(r) for r in guidance_actions],
        "s2_confirmed": s2_map.get("confirmed", 0) + s2_map.get("upgraded", 0),
        "s2_downgraded": s2_map.get("downgraded", 0),
        "s2_false_positive": s2_map.get("false_positive", 0),
        "s2_total": sum(s2_map.values()),
        "active_challenges": active_challenges,
        "dimension_averages": dict(dim_avgs) if dim_avgs else {},
    }


def get_heatmap_data(conn):
    """Scatter plot data: legal challenge vs policy priority per rule."""
    rows = conn.execute(
        """SELECT fr_citation, title, composite_score,
                  legal_challenge_subcomposite, policy_priority_subcomposite,
                  comment_multiplier, action_category
           FROM stage1_scores
           WHERE legal_challenge_subcomposite IS NOT NULL
           ORDER BY composite_score DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_challenges(conn):
    """Active/pending legal challenges for dashboard alert panel."""
    rows = conn.execute(
        """SELECT ch.*, s.title as rule_title, s.composite_score, s.action_category
           FROM stage1_challenge_history ch
           LEFT JOIN stage1_scores s ON ch.fr_citation = s.fr_citation
           WHERE ch.current_status IN ('pending', 'good_law')
           ORDER BY ch.date_decided DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


# ── Analytics ─────────────────────────────────────────────────────────

def get_analytics_by_theory(conn):
    """Count rules per legal theory tag."""
    rows = conn.execute(
        "SELECT legal_theory_tags FROM stage1_scores WHERE legal_theory_tags IS NOT NULL"
    ).fetchall()

    counts = {}
    for r in rows:
        tags = _parse_json_field(r["legal_theory_tags"])
        for tag in tags:
            counts[tag] = counts.get(tag, 0) + 1

    return sorted(
        [{"theory": k, "count": v} for k, v in counts.items()],
        key=lambda x: x["count"], reverse=True,
    )


def get_analytics_by_era(conn):
    """Rules grouped by publication year with avg composite."""
    rows = conn.execute(
        """SELECT SUBSTR(publication_date, 1, 4) as year,
                  COUNT(*) as count,
                  AVG(composite_score) as avg_composite,
                  AVG(dim1_composite) as avg_loper,
                  AVG(dim2_composite) as avg_mq
           FROM stage1_scores
           WHERE publication_date IS NOT NULL
           GROUP BY SUBSTR(publication_date, 1, 4)
           ORDER BY year"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_analytics_by_provision(conn):
    """Top CEA provisions by vulnerable rule count."""
    rows = conn.execute(
        "SELECT primary_statutory_authority FROM stage1_scores"
    ).fetchall()

    provision_rules = {}
    provision_scores = {}
    for r in rows:
        sections = _parse_json_field(r["primary_statutory_authority"])
        for sec in sections:
            provision_rules[sec] = provision_rules.get(sec, 0) + 1
            provision_scores.setdefault(sec, [])

    # Get avg scores per provision
    for r in conn.execute(
        "SELECT primary_statutory_authority, composite_score FROM stage1_scores"
    ).fetchall():
        sections = _parse_json_field(r["primary_statutory_authority"])
        for sec in sections:
            provision_scores[sec].append(r["composite_score"] or 0)

    result = []
    for sec, count in provision_rules.items():
        scores = provision_scores.get(sec, [])
        avg = sum(scores) / len(scores) if scores else 0
        result.append({"provision": sec, "rule_count": count, "avg_composite": round(avg, 2)})

    return sorted(result, key=lambda x: x["rule_count"], reverse=True)[:20]


def get_analytics_dimension_correlation(conn):
    """All rules with D1 and D5 composites for scatter plot."""
    rows = conn.execute(
        """SELECT fr_citation, title, dim1_composite, dim5_composite,
                  composite_score, action_category
           FROM stage1_scores
           WHERE dim1_composite IS NOT NULL AND dim5_composite IS NOT NULL"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_analytics_compound_vulnerability(conn):
    """Rules with 3+ legal theory tags."""
    rows = conn.execute(
        """SELECT fr_citation, title, composite_score, action_category,
                  legal_theory_tags
           FROM stage1_scores
           WHERE legal_theory_tags IS NOT NULL
           ORDER BY composite_score DESC"""
    ).fetchall()

    result = []
    for r in rows:
        tags = _parse_json_field(r["legal_theory_tags"])
        if len(tags) >= 3:
            d = dict(r)
            d["legal_theory_tags"] = tags
            d["tag_count"] = len(tags)
            result.append(d)

    return sorted(result, key=lambda x: x["tag_count"], reverse=True)
