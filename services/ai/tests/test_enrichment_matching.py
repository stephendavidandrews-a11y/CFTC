"""Person matching, organization resolution, and domain resolution order."""


from app.enrichment.matching import (
    MATCH_EMAIL,
    MATCH_NAME_FUZZY,
    MATCH_NAME_ORG,
    ORG_BY_DOMAIN,
    ORG_BY_NAME_EXACT,
    ORG_BY_NAME_FUZZY,
    ORG_PROPOSED_NEW,
    match_person,
    name_similarity,
    needs_lookup,
    normalize_org_name,
    normalize_person_name,
    resolve_domain,
    resolve_organization,
)

PEOPLE = [
    {
        "id": "p1",
        "full_name": "Jane Doe",
        "email": "jane.doe@cftc.gov",
        "organization_id": "o1",
        "email_verification_status": "deliverable",
    },
    {
        "id": "p2",
        "full_name": "Jonathan Smith",
        "email": None,
        "organization_id": "o1",
        "email_verification_status": None,
    },
    {
        "id": "p3",
        "full_name": "Jane Doe",
        "email": None,
        "organization_id": "o2",
        "email_verification_status": None,
    },
    {
        "id": "p4",
        "full_name": "Robert Jones",
        "email": None,
        "organization_id": None,
        "email_verification_status": None,
    },
]

ORGS = [
    {"id": "o1", "name": "Commodity Futures Trading Commission",
     "short_name": "CFTC", "primary_domain": "cftc.gov"},
    {"id": "o2", "name": "Acme Corporation", "short_name": "Acme",
     "primary_domain": None},
    {"id": "o3", "name": "Beta Holdings LLC", "short_name": None,
     "primary_domain": "beta.com"},
]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def test_normalize_person_name_drops_honorifics_and_punctuation():
    assert normalize_person_name("Dr. Jane  Doe, Jr.") == "jane doe"


def test_normalize_org_name_strips_corporate_noise():
    assert normalize_org_name("Acme Corporation, Inc.") == "acme"
    assert normalize_org_name("Beta Holdings LLC") == "beta"


def test_normalize_org_name_keeps_something_when_all_noise():
    # "The Company" is all noise words; must not collapse to empty.
    assert normalize_org_name("The Company") != ""


# ---------------------------------------------------------------------------
# Name similarity
# ---------------------------------------------------------------------------


def test_identical_names_score_one():
    assert name_similarity("Jane Doe", "jane doe") == 1.0


def test_nickname_shares_surname_and_prefix():
    assert name_similarity("Jon Smith", "Jonathan Smith") >= 0.90


def test_initial_against_given_name():
    assert name_similarity("J Smith", "Jane Smith") >= 0.85


def test_different_people_score_low():
    assert name_similarity("Jane Doe", "Robert Jones") < 0.6


def test_empty_name_scores_zero():
    assert name_similarity("", "Jane Doe") == 0.0


# ---------------------------------------------------------------------------
# Person matching tiers
# ---------------------------------------------------------------------------


def test_email_match_wins_and_is_certain():
    row = {"email": "JANE.DOE@cftc.gov", "full_name": "Totally Different Name"}
    pid, method, conf, ambiguous = match_person(row, PEOPLE)
    assert (pid, method, conf, ambiguous) == ("p1", MATCH_EMAIL, 1.0, False)


def test_name_plus_org_match():
    row = {"email": "", "full_name": "Jane Doe", "resolved_organization_id": "o2"}
    pid, method, conf, ambiguous = match_person(row, PEOPLE)
    assert pid == "p3"
    assert method == MATCH_NAME_ORG
    assert conf == 0.9
    assert ambiguous is False


def test_fuzzy_match_within_org():
    row = {"email": "", "full_name": "Jon Smith", "resolved_organization_id": "o1"}
    pid, method, conf, ambiguous = match_person(row, PEOPLE)
    assert pid == "p2"
    assert method == MATCH_NAME_FUZZY
    assert conf >= 0.85
    assert ambiguous is False, "same-org fuzzy match with one candidate is not ambiguous"


def test_fuzzy_match_without_org_is_ambiguous():
    """No org to corroborate means a human decides."""
    row = {"email": "", "full_name": "Jon Smith"}
    pid, _method, _conf, ambiguous = match_person(row, PEOPLE)
    assert pid == "p2"
    assert ambiguous is True


def test_same_name_in_two_orgs_without_org_context_is_ambiguous():
    row = {"email": "", "full_name": "Jane Doe"}
    _pid, _method, _conf, ambiguous = match_person(row, PEOPLE)
    assert ambiguous is True, "two Jane Does must not silently resolve to one"


def test_no_match_returns_none():
    row = {"email": "", "full_name": "Wholly Unknown Person"}
    assert match_person(row, PEOPLE) == (None, None, None, False)


def test_blank_name_and_no_email_matches_nothing():
    assert match_person({"email": "", "full_name": "   "}, PEOPLE) == (
        None, None, None, False,
    )


def test_threshold_is_respected():
    row = {"email": "", "full_name": "Jon Smith", "resolved_organization_id": "o1"}
    # An impossible threshold should suppress the fuzzy tier entirely.
    assert match_person(row, PEOPLE, fuzzy_threshold=0.999)[0] is None


# ---------------------------------------------------------------------------
# Organization resolution
# ---------------------------------------------------------------------------


def test_org_resolved_by_domain_first():
    row = {"domain": "cftc.gov", "org_name": "Something Else Entirely"}
    assert resolve_organization(row, ORGS) == ("o1", ORG_BY_DOMAIN)


def test_org_resolved_by_exact_name_ignoring_suffix():
    row = {"domain": "", "org_name": "Acme Corporation Inc"}
    assert resolve_organization(row, ORGS) == ("o2", ORG_BY_NAME_EXACT)


def test_org_resolved_by_short_name():
    row = {"domain": "", "org_name": "CFTC"}
    assert resolve_organization(row, ORGS) == ("o1", ORG_BY_NAME_EXACT)


def test_org_fuzzy_match():
    row = {"domain": "", "org_name": "Acme Corpration"}  # typo
    org_id, method = resolve_organization(row, ORGS)
    assert org_id == "o2"
    assert method in (ORG_BY_NAME_EXACT, ORG_BY_NAME_FUZZY)


def test_unknown_org_is_proposed_new():
    row = {"domain": "", "org_name": "Zzyzx Unrelated Entity"}
    assert resolve_organization(row, ORGS) == (None, ORG_PROPOSED_NEW)


def test_no_org_name_resolves_to_nothing():
    assert resolve_organization({"domain": "", "org_name": ""}, ORGS) == (None, None)


def test_free_email_domain_does_not_match_an_org():
    row = {"domain": "gmail.com", "org_name": ""}
    assert resolve_organization(row, ORGS) == (None, None)


# ---------------------------------------------------------------------------
# Domain resolution order
# ---------------------------------------------------------------------------


def test_sheet_domain_wins():
    row = {"domain": "explicit.gov", "email": "x@other.com"}
    assert resolve_domain(row, ORGS, "o1") == ("explicit.gov", "sheet")


def test_email_domain_used_when_no_explicit_domain():
    row = {"domain": "", "email": "jane@fromemail.gov"}
    assert resolve_domain(row, ORGS, None) == ("fromemail.gov", "email")


def test_org_primary_domain_is_third():
    row = {"domain": "", "email": ""}
    assert resolve_domain(row, ORGS, "o1") == ("cftc.gov", "organization")


def test_org_without_primary_domain_leaves_row_unresolved():
    row = {"domain": "", "email": ""}
    assert resolve_domain(row, ORGS, "o2") == ("", "unresolved")


def test_no_domain_anywhere_is_unresolved():
    assert resolve_domain({"domain": "", "email": ""}, ORGS, None) == ("", "unresolved")


def test_webmail_domain_is_treated_as_no_domain():
    """Hunter cannot find a work address at gmail.com; do not spend a credit."""
    row = {"domain": "gmail.com", "email": ""}
    assert resolve_domain(row, ORGS, None) == ("", "free_email")


def test_webmail_email_is_treated_as_no_domain():
    row = {"domain": "", "email": "someone@yahoo.com"}
    assert resolve_domain(row, ORGS, None) == ("", "free_email")


# ---------------------------------------------------------------------------
# needs_lookup — the credit-saving gate
# ---------------------------------------------------------------------------


def test_row_with_email_in_sheet_needs_no_lookup():
    row = {"email": "jane@x.gov", "domain": "x.gov", "first_name": "J", "last_name": "D"}
    assert needs_lookup(row, None) == (False, "email_in_sheet")


def test_person_with_verified_email_needs_no_lookup():
    row = {"email": "", "domain": "cftc.gov", "first_name": "Jane", "last_name": "Doe"}
    person = {"email": "jane.doe@cftc.gov", "email_verification_status": "deliverable"}
    assert needs_lookup(row, person) == (False, "already_verified")


def test_person_with_unverified_email_still_needs_lookup():
    row = {"email": "", "domain": "cftc.gov", "first_name": "Jane", "last_name": "Doe"}
    person = {"email": "guess@cftc.gov", "email_verification_status": None}
    assert needs_lookup(row, person)[0] is True


def test_row_without_domain_needs_no_lookup():
    row = {"email": "", "domain": "", "first_name": "Jane", "last_name": "Doe"}
    assert needs_lookup(row, None) == (False, "no_domain")


def test_row_without_full_name_pair_needs_no_lookup():
    row = {"email": "", "domain": "cftc.gov", "first_name": "Jane", "last_name": ""}
    assert needs_lookup(row, None) == (False, "incomplete_name")


def test_complete_new_row_needs_lookup():
    row = {"email": "", "domain": "cftc.gov", "first_name": "Jane", "last_name": "Doe"}
    assert needs_lookup(row, None) == (True, "lookup")
