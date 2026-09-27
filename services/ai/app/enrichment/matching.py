"""Resolve sheet rows against existing tracker people and organizations.

Runs before any Hunter call, so the pre-flight can say honestly how many rows
actually need paying for. Two jobs:

  1. Person matching — is this row someone the tracker already knows?
  2. Domain resolution — what domain should Hunter search, and which org is it?

The fuzzy tier exists because a sheet says "Jon Smith" when the tracker says
"Jonathan Smith". An ambiguous match is never auto-accepted downstream.
"""

import logging
import re
from difflib import SequenceMatcher

from app.enrichment.parsing import (
    domain_from_email,
    is_free_email_domain,
    normalize_domain,
)

logger = logging.getLogger(__name__)

MATCH_EMAIL = "email"
MATCH_NAME_ORG = "name_org"
MATCH_NAME_FUZZY = "name_fuzzy"

ORG_BY_DOMAIN = "domain"
ORG_BY_NAME_EXACT = "name_exact"
ORG_BY_NAME_FUZZY = "name_fuzzy"
ORG_PROPOSED_NEW = "proposed_new"

# Corporate/agency suffixes that carry no identifying signal when comparing names.
_ORG_NOISE = {
    "inc", "llc", "llp", "lp", "ltd", "plc", "co", "corp", "corporation",
    "company", "group", "holdings", "partners", "associates", "the", "and",
    "of", "commission", "department", "dept", "agency", "office", "bureau",
    "administration", "authority", "us", "usa", "u.s.", "federal", "national",
}


def normalize_person_name(name: str) -> str:
    """Casefold, drop punctuation and honorifics — for comparison only."""
    text = re.sub(r"[^\w\s]", " ", (name or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    drop = {"mr", "mrs", "ms", "miss", "dr", "prof", "jr", "sr", "ii", "iii", "iv"}
    return " ".join(p for p in text.split() if p not in drop)


def normalize_org_name(name: str) -> str:
    """Casefold and strip corporate noise words, so 'Acme Inc.' == 'Acme'."""
    text = re.sub(r"[^\w\s]", " ", (name or "").lower())
    text = re.sub(r"\s+", " ", text).strip()
    kept = [p for p in text.split() if p not in _ORG_NOISE]
    return " ".join(kept) if kept else text


def name_similarity(a: str, b: str) -> float:
    """0..1 similarity between two person names, order-insensitive on tokens."""
    na, nb = normalize_person_name(a), normalize_person_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0

    ratio = SequenceMatcher(None, na, nb).ratio()

    # Reward a shared surname with a compatible given name, which is the common
    # "Jon Smith" vs "Jonathan Smith" case.
    ta, tb = na.split(), nb.split()
    if ta and tb and ta[-1] == tb[-1]:
        first_a, first_b = ta[0], tb[0]
        if first_a == first_b:
            return max(ratio, 0.97)
        if first_a.startswith(first_b) or first_b.startswith(first_a):
            return max(ratio, 0.90)
        # Initial against full given name: "J Smith" vs "Jane Smith".
        if (len(first_a) == 1 or len(first_b) == 1) and first_a[0] == first_b[0]:
            return max(ratio, 0.86)
    return ratio


def match_person(
    row: dict,
    people: list[dict],
    fuzzy_threshold: float = 0.85,
) -> tuple[str | None, str | None, float | None, bool]:
    """Match one mapped row against the tracker's people.

    Returns (person_id, method, confidence, ambiguous).

    Tiers, first hit wins:
      1. exact email             -> 1.0
      2. name + same org         -> 0.9
      3. fuzzy name in same org  -> the similarity score
      4. fuzzy name, no org      -> the similarity score, but ambiguous

    `ambiguous` is True when more than one candidate scored at or above the
    threshold, or when a fuzzy match had no organization to corroborate it. The
    proposal layer refuses to auto-accept an ambiguous match.
    """
    email = (row.get("email") or "").strip().lower()
    org_id = row.get("resolved_organization_id")
    full_name = row.get("full_name") or ""

    if email:
        for p in people:
            if (p.get("email") or "").strip().lower() == email:
                return p["id"], MATCH_EMAIL, 1.0, False

    if not normalize_person_name(full_name):
        return None, None, None, False

    target = normalize_person_name(full_name)

    if org_id:
        exact_in_org = [
            p
            for p in people
            if p.get("organization_id") == org_id
            and normalize_person_name(p.get("full_name") or "") == target
        ]
        if len(exact_in_org) == 1:
            return exact_in_org[0]["id"], MATCH_NAME_ORG, 0.9, False
        if len(exact_in_org) > 1:
            return exact_in_org[0]["id"], MATCH_NAME_ORG, 0.9, True

    # Fuzzy, preferring same-org candidates.
    scored = []
    for p in people:
        score = name_similarity(full_name, p.get("full_name") or "")
        if score >= fuzzy_threshold:
            same_org = bool(org_id) and p.get("organization_id") == org_id
            scored.append((score, same_org, p["id"]))

    if not scored:
        return None, None, None, False

    scored.sort(key=lambda t: (t[1], t[0]), reverse=True)
    best_score, best_same_org, best_id = scored[0]

    # More than one plausible person is a decision for a human.
    ambiguous = len(scored) > 1 or not best_same_org
    return best_id, MATCH_NAME_FUZZY, round(best_score, 3), ambiguous


def resolve_organization(
    row: dict,
    organizations: list[dict],
    fuzzy_threshold: float = 0.85,
) -> tuple[str | None, str | None]:
    """Resolve the row's org name to a tracker organization.

    Returns (organization_id, method). Method ORG_PROPOSED_NEW means no existing
    org matched and the operator may want a new one.
    """
    domain = normalize_domain(row.get("domain") or "")
    org_name = (row.get("org_name") or "").strip()

    if domain and not is_free_email_domain(domain):
        for o in organizations:
            if normalize_domain(o.get("primary_domain") or "") == domain:
                return o["id"], ORG_BY_DOMAIN

    if not org_name:
        return None, None

    target = normalize_org_name(org_name)
    if not target:
        return None, None

    exact = [o for o in organizations if normalize_org_name(o.get("name") or "") == target]
    if exact:
        return exact[0]["id"], ORG_BY_NAME_EXACT

    # Short names are a common shorthand in spreadsheets ("CFTC").
    for o in organizations:
        short = normalize_org_name(o.get("short_name") or "")
        if short and short == target:
            return o["id"], ORG_BY_NAME_EXACT

    best_id, best_score = None, 0.0
    for o in organizations:
        score = _org_similarity(org_name, o.get("name") or "")
        if score > best_score:
            best_id, best_score = o["id"], score
    if best_id and best_score >= fuzzy_threshold:
        return best_id, ORG_BY_NAME_FUZZY

    return None, ORG_PROPOSED_NEW


def _org_similarity(a: str, b: str) -> float:
    """Best similarity across both the stripped and unstripped forms.

    Stripping noise words is asymmetric when one side has a typo in its suffix:
    "Acme Corpration" keeps the typo while "Acme Corporation" collapses to
    "acme", which tanks the ratio. Comparing both forms and taking the better
    score catches the typo without loosening the threshold.
    """
    plain_a = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (a or "").lower())).strip()
    plain_b = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (b or "").lower())).strip()
    stripped_a, stripped_b = normalize_org_name(a), normalize_org_name(b)
    scores = [
        SequenceMatcher(None, plain_a, plain_b).ratio(),
        SequenceMatcher(None, stripped_a, stripped_b).ratio(),
    ]
    return max(scores)


def resolve_domain(
    row: dict,
    organizations: list[dict],
    org_id: str | None,
) -> tuple[str, str]:
    """Decide which domain Hunter should search for this row.

    Order, first hit wins:
      1. explicit domain column in the sheet
      2. domain parsed from an email already in the sheet
      3. primary_domain of the resolved organization
      4. nothing — the row needs a domain before it can be looked up

    A webmail domain (gmail.com and friends) is treated as no domain: Hunter
    cannot find someone's work address at gmail.com, and spending a credit to
    learn that is waste.

    Returns (domain, method). An empty domain means the row must be held.
    """
    explicit = normalize_domain(row.get("domain") or "")
    if explicit and not is_free_email_domain(explicit):
        return explicit, "sheet"
    if explicit and is_free_email_domain(explicit):
        return "", "free_email"

    from_email = domain_from_email(row.get("email") or "")
    if from_email and not is_free_email_domain(from_email):
        return from_email, "email"
    if from_email and is_free_email_domain(from_email):
        return "", "free_email"

    if org_id:
        for o in organizations:
            if o["id"] == org_id:
                org_domain = normalize_domain(o.get("primary_domain") or "")
                if org_domain:
                    return org_domain, "organization"
                break

    return "", "unresolved"


def needs_lookup(row: dict, person: dict | None) -> tuple[bool, str]:
    """Should this row cost a Hunter credit?

    Returns (needs_lookup, reason). A row is skipped when the sheet already has
    an email, or when the matched person already has a verified one — there is
    nothing to find.
    """
    if (row.get("email") or "").strip():
        return False, "email_in_sheet"

    if person:
        existing = (person.get("email") or "").strip()
        verified = (person.get("email_verification_status") or "").strip().lower()
        if existing and verified == "deliverable":
            return False, "already_verified"

    if not (row.get("domain") or "").strip():
        return False, "no_domain"

    if not ((row.get("first_name") or "").strip() and (row.get("last_name") or "").strip()):
        return False, "incomplete_name"

    return True, "lookup"
