"""Spreadsheet parsing, header mapping, and name splitting."""

import io

import pytest
from app.enrichment.parsing import (
    SOURCE_LINKEDIN,
    SOURCE_SPREADSHEET,
    ParseError,
    apply_mapping,
    domain_from_email,
    is_free_email_domain,
    is_linkedin_export,
    normalize_domain,
    normalize_header,
    parse_file,
    propose_mapping,
    split_full_name,
    validate_mapping,
)

# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_parse_simple_csv():
    content = b"First Name,Last Name,Company\nJane,Doe,Acme Corp\nJohn,Roe,Beta LLC\n"
    headers, rows = parse_file(content, "contacts.csv")
    assert headers == ["First Name", "Last Name", "Company"]
    assert len(rows) == 2
    assert rows[0]["First Name"] == "Jane"
    assert rows[1]["Company"] == "Beta LLC"


def test_blank_rows_are_dropped():
    content = b"Name,Company\nJane Doe,Acme\n,\n\nJohn Roe,Beta\n"
    _, rows = parse_file(content, "c.csv")
    assert len(rows) == 2


def test_semicolon_delimiter_is_sniffed():
    content = b"First Name;Last Name;Company\nJane;Doe;Acme\n"
    headers, rows = parse_file(content, "c.csv")
    assert headers == ["First Name", "Last Name", "Company"]
    assert rows[0]["Company"] == "Acme"


def test_tsv_uses_tabs():
    content = b"First Name\tLast Name\tCompany\nJane\tDoe\tAcme\n"
    headers, rows = parse_file(content, "c.tsv")
    assert headers == ["First Name", "Last Name", "Company"]
    assert rows[0]["Last Name"] == "Doe"


def test_utf8_bom_is_stripped():
    content = "﻿First Name,Last Name\nJane,Doe\n".encode()
    headers, _ = parse_file(content, "c.csv")
    assert headers[0] == "First Name", "BOM must not corrupt the first header"


def test_cp1252_fallback_decodes():
    content = "Name,Company\nJos\xe9 Garc\xeda,Acme\n".encode("cp1252")
    _, rows = parse_file(content, "c.csv")
    assert "Garc" in rows[0]["Name"]


def test_empty_file_is_rejected():
    with pytest.raises(ParseError):
        parse_file(b"", "c.csv")


def test_linkedin_preamble_is_skipped():
    """LinkedIn's export opens with a Notes: preamble before the real header."""
    content = (
        b'Notes:\n"When exporting your connection data..."\n\n'
        b"First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
        b"Jane,Doe,https://www.linkedin.com/in/janedoe,,Acme Corp,Counsel,01 Jan 2024\n"
    )
    headers, rows = parse_file(content, "Connections.csv")
    assert "First Name" in headers
    assert len(rows) == 1
    assert rows[0]["Company"] == "Acme Corp"


# ---------------------------------------------------------------------------
# XLSX
# ---------------------------------------------------------------------------


def _xlsx_bytes(rows):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_xlsx():
    content = _xlsx_bytes(
        [["First Name", "Last Name", "Company"], ["Jane", "Doe", "Acme"]]
    )
    headers, rows = parse_file(content, "contacts.xlsx")
    assert headers == ["First Name", "Last Name", "Company"]
    assert rows[0]["First Name"] == "Jane"


def test_xlsx_leading_blank_rows_skipped():
    content = _xlsx_bytes(
        [[None, None], ["First Name", "Company"], ["Jane", "Acme"]]
    )
    headers, rows = parse_file(content, "c.xlsx")
    assert headers == ["First Name", "Company"]
    assert len(rows) == 1


def test_xlsx_duplicate_headers_are_disambiguated():
    content = _xlsx_bytes([["Name", "Name"], ["a", "b"]])
    headers, rows = parse_file(content, "c.xlsx")
    assert len(set(headers)) == 2, "duplicate headers must not collide as dict keys"
    assert len(rows) == 1


def test_corrupt_xlsx_raises_parse_error():
    with pytest.raises(ParseError):
        parse_file(b"this is not a workbook", "c.xlsx")


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------


def test_linkedin_preset_maps_known_headers():
    headers = [
        "First Name",
        "Last Name",
        "URL",
        "Email Address",
        "Company",
        "Position",
        "Connected On",
    ]
    mapping = propose_mapping(headers, SOURCE_LINKEDIN)
    assert mapping["First Name"] == "first_name"
    assert mapping["URL"] == "linkedin_url"
    assert mapping["Email Address"] == "email"
    assert mapping["Company"] == "org_name"
    assert mapping["Position"] == "title"
    # Connected On has no canonical target and is left unmapped.
    assert "Connected On" not in mapping


def test_is_linkedin_export_detection():
    assert is_linkedin_export(["First Name", "Last Name", "Company", "Position"])
    assert not is_linkedin_export(["Email", "Notes"])


def test_heuristics_map_common_headers():
    headers = ["Full Name", "Organisation", "Job Title", "E-Mail", "Website"]
    mapping = propose_mapping(headers, SOURCE_SPREADSHEET)
    assert mapping["Full Name"] == "full_name"
    assert mapping["Organisation"] == "org_name"
    assert mapping["Job Title"] == "title"
    assert mapping["E-Mail"] == "email"
    assert mapping["Website"] == "domain"


def test_email_address_beats_generic_address():
    mapping = propose_mapping(["Email Address", "Mailing Address"], SOURCE_SPREADSHEET)
    assert mapping.get("Email Address") == "email"
    assert mapping.get("Mailing Address") != "email"


def test_one_field_is_not_claimed_twice():
    mapping = propose_mapping(["Name", "Contact Name"], SOURCE_SPREADSHEET)
    assert list(mapping.values()).count("full_name") == 1


def test_normalize_header_handles_punctuation_and_case():
    assert normalize_header("  First   Name: ") == "first name"
    assert normalize_header(None) == ""


# ---------------------------------------------------------------------------
# Mapping validation
# ---------------------------------------------------------------------------


def test_valid_mapping_has_no_problems():
    mapping = {"A": "first_name", "B": "last_name", "C": "org_name"}
    assert validate_mapping(mapping) == []


def test_mapping_without_a_name_is_rejected():
    problems = validate_mapping({"A": "org_name"})
    assert any("name column" in p for p in problems)


def test_mapping_without_a_domain_source_is_rejected():
    problems = validate_mapping({"A": "full_name", "B": "title"})
    assert any("domain source" in p for p in problems)


def test_duplicate_target_fields_are_rejected():
    problems = validate_mapping(
        {"A": "full_name", "B": "full_name", "C": "org_name"}
    )
    assert any("same field" in p for p in problems)


def test_unknown_target_field_is_rejected():
    problems = validate_mapping({"A": "full_name", "B": "org_name", "C": "nonsense"})
    assert any("Unknown target fields" in p for p in problems)


def test_first_plus_last_satisfies_the_name_requirement():
    assert validate_mapping({"A": "first_name", "B": "last_name", "C": "domain"}) == []


# ---------------------------------------------------------------------------
# Name splitting
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Jane Doe", ("Jane", "Doe")),
        ("Doe, Jane", ("Jane", "Doe")),
        ("Jane Q. Doe", ("Jane", "Doe")),
        ("Jane van der Berg", ("Jane", "van der Berg")),
        ("Dr. Jane Doe", ("Jane", "Doe")),
        ("Jane Doe Jr.", ("Jane", "Doe")),
        ("Jane Doe, PhD", ("Jane", "Doe")),
        ("Doe, Jane Q.", ("Jane", "Doe")),
        ("Jane Doe (she/her)", ("Jane", "Doe")),
        ("Jane", ("Jane", "")),
        ("", ("", "")),
        ("   ", ("", "")),
    ],
)
def test_split_full_name(raw, expected):
    assert split_full_name(raw) == expected


# ---------------------------------------------------------------------------
# Domain normalization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.gov", "example.gov"),
        ("WWW.Example.GOV", "example.gov"),
        ("https://www.example.gov/about?x=1", "example.gov"),
        ("http://example.gov:8080", "example.gov"),
        ("jane@example.gov", "example.gov"),
        ("localhost", ""),
        ("not a domain", ""),
        ("", ""),
        ("example.", ""),
    ],
)
def test_normalize_domain(raw, expected):
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("jane@example.gov", "example.gov"),
        ("Jane.Doe@Example.GOV", "example.gov"),
        ("jane@localhost", ""),
        ("notanemail", ""),
        ("", ""),
    ],
)
def test_domain_from_email(raw, expected):
    assert domain_from_email(raw) == expected


def test_free_email_domains_are_flagged():
    assert is_free_email_domain("gmail.com")
    assert is_free_email_domain("GMAIL.COM")
    assert not is_free_email_domain("cftc.gov")


# ---------------------------------------------------------------------------
# apply_mapping
# ---------------------------------------------------------------------------


def test_apply_mapping_derives_first_last_from_full_name():
    row = {"Name": "Jane Doe", "Co": "Acme"}
    out = apply_mapping(row, {"Name": "full_name", "Co": "org_name"})
    assert out["first_name"] == "Jane"
    assert out["last_name"] == "Doe"
    assert out["org_name"] == "Acme"


def test_apply_mapping_builds_full_name_from_parts():
    row = {"F": "Jane", "L": "Doe"}
    out = apply_mapping(row, {"F": "first_name", "L": "last_name"})
    assert out["full_name"] == "Jane Doe"


def test_apply_mapping_takes_domain_from_email_when_absent():
    row = {"N": "Jane Doe", "E": "jane@example.gov"}
    out = apply_mapping(row, {"N": "full_name", "E": "email"})
    assert out["domain"] == "example.gov"


def test_explicit_domain_column_wins_over_email():
    row = {"N": "Jane Doe", "E": "jane@personal.com", "D": "work.gov"}
    out = apply_mapping(row, {"N": "full_name", "E": "email", "D": "domain"})
    assert out["domain"] == "work.gov"


def test_apply_mapping_always_returns_every_canonical_field():
    out = apply_mapping({"N": "Jane Doe"}, {"N": "full_name"})
    for field in ("first_name", "last_name", "full_name", "org_name", "domain",
                  "title", "email", "linkedin_url"):
        assert field in out


def test_linkedin_row_maps_end_to_end():
    """A real LinkedIn export row, through the preset, ready for Hunter."""
    headers = ["First Name", "Last Name", "URL", "Email Address", "Company",
               "Position", "Connected On"]
    row = {
        "First Name": "Jane",
        "Last Name": "Doe",
        "URL": "https://www.linkedin.com/in/janedoe",
        "Email Address": "",
        "Company": "Acme Corp",
        "Position": "Senior Counsel",
        "Connected On": "01 Jan 2024",
    }
    mapping = propose_mapping(headers, SOURCE_LINKEDIN)
    assert validate_mapping(mapping) == []
    out = apply_mapping(row, mapping)
    assert out["first_name"] == "Jane"
    assert out["last_name"] == "Doe"
    assert out["org_name"] == "Acme Corp"
    assert out["title"] == "Senior Counsel"
    assert out["linkedin_url"] == "https://www.linkedin.com/in/janedoe"
    # No email in the sheet: this is exactly the row Hunter should fill.
    assert out["email"] == ""
