"""Spreadsheet parsing and column mapping for contact enrichment.

Two source shapes:
  - 'spreadsheet'     arbitrary headers; the operator confirms a proposed mapping
  - 'linkedin_export' LinkedIn's own data export, fixed headers, no mapping needed

Nothing here touches the network. Parsing and mapping happen before a single
Hunter credit is spent, so a malformed sheet costs nothing.
"""

import csv
import io
import logging
import re

logger = logging.getLogger(__name__)

SOURCE_SPREADSHEET = "spreadsheet"
SOURCE_LINKEDIN = "linkedin_export"

# The fields the rest of the pipeline understands.
CANONICAL_FIELDS = (
    "first_name",
    "last_name",
    "full_name",
    "org_name",
    "domain",
    "title",
    "email",
    "linkedin_url",
)

# LinkedIn's export header -> canonical field. Their CSV has a fixed shape, so
# this is a preset rather than a guess.
LINKEDIN_PRESET = {
    "first name": "first_name",
    "last name": "last_name",
    "url": "linkedin_url",
    "email address": "email",
    "company": "org_name",
    "position": "title",
}

# Header-name heuristics for generic sheets, most specific first. Each entry is
# (compiled pattern, canonical field). Order matters: "email address" must beat
# "address", and "company domain" must beat "company".
_HEURISTICS = [
    (r"^linked\s*in(\s*(url|profile|link))?$", "linkedin_url"),
    (r"linkedin", "linkedin_url"),
    (r"^(e[-\s]?mail|email)(\s*address)?$", "email"),
    (r"e[-\s]?mail", "email"),
    (r"(web\s*)?domain|website|web\s*site|url\s*domain", "domain"),
    (r"^(first|given|fore)\s*name$|^fname$", "first_name"),
    (r"^(last|sur|family)\s*name$|^lname$", "last_name"),
    (r"^(full\s*name|name|contact\s*name|person)$", "full_name"),
    (r"(job\s*)?(title|position|role|job)$", "title"),
    (r"company|organi[sz]ation|employer|firm|agency|org$", "org_name"),
]


class ParseError(ValueError):
    """The uploaded file could not be read as a contact sheet."""


def normalize_header(header: str) -> str:
    """Lowercase, collapse whitespace, drop surrounding punctuation."""
    if header is None:
        return ""
    return re.sub(r"\s+", " ", str(header)).strip().strip(":*#").strip().lower()


def parse_file(content: bytes, filename: str) -> tuple[list[str], list[dict]]:
    """Parse an uploaded sheet into (headers, rows).

    Rows are dicts keyed by the original header text, values as strings.
    Raises ParseError for anything unreadable.
    """
    lower = (filename or "").lower()
    if lower.endswith((".xlsx", ".xlsm", ".xltx")):
        return _parse_xlsx(content)
    if lower.endswith((".csv", ".tsv", ".txt")):
        return _parse_csv(content, tab="\t" if lower.endswith(".tsv") else None)
    # No usable extension: try CSV, since that is what exports usually are.
    return _parse_csv(content, tab=None)


def _decode(content: bytes) -> str:
    """Decode with the encodings real exports actually use.

    LinkedIn ships UTF-8 with a BOM; older tooling ships cp1252.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ParseError("Could not decode file as text (tried UTF-8, cp1252, latin-1)")


def _parse_csv(content: bytes, tab: str | None) -> tuple[list[str], list[dict]]:
    if not content:
        raise ParseError("File is empty")
    text = _decode(content)

    # LinkedIn prefixes its connections export with a "Notes:" preamble followed
    # by a blank line. Skip anything before the real header row.
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines[:12]):
        if _looks_like_header(line):
            start = i
            break
    text = "\n".join(lines[start:])

    if tab:
        delimiter = tab
    else:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ParseError("No header row found")
    headers = [h for h in reader.fieldnames if h and h.strip()]
    if not headers:
        raise ParseError("No header row found")

    rows = []
    for raw in reader:
        row = {
            k: ("" if v is None else str(v).strip())
            for k, v in raw.items()
            if k and k.strip()
        }
        if any(row.values()):
            rows.append(row)
    return headers, rows


def _looks_like_header(line: str) -> bool:
    """A header row mentions at least one field we know how to map."""
    norm = line.lower()
    return any(
        token in norm
        for token in ("first name", "last name", "email", "company", "name", "domain")
    )


def _parse_xlsx(content: bytes) -> tuple[list[str], list[dict]]:
    try:
        import openpyxl
    except ImportError as e:  # pragma: no cover - dependency is declared
        raise ParseError("openpyxl is required to read .xlsx files") from e

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as e:
        raise ParseError(f"Could not read workbook: {e}") from e

    try:
        ws = wb.active
        if ws is None:
            raise ParseError("Workbook has no active sheet")

        rows_iter = ws.iter_rows(values_only=True)
        headers: list[str] = []
        for raw in rows_iter:
            if raw is None:
                continue
            candidate = ["" if c is None else str(c).strip() for c in raw]
            if any(candidate):
                headers = candidate
                break
        if not headers:
            raise ParseError("No header row found")

        # Deduplicate blank/repeated headers so dict keys stay distinct.
        seen: dict[str, int] = {}
        clean_headers = []
        for i, h in enumerate(headers):
            name = h or f"column_{i + 1}"
            if name in seen:
                seen[name] += 1
                name = f"{name}_{seen[name]}"
            else:
                seen[name] = 0
            clean_headers.append(name)

        rows = []
        for raw in rows_iter:
            if raw is None:
                continue
            values = ["" if c is None else str(c).strip() for c in raw]
            row = {
                clean_headers[i]: values[i]
                for i in range(min(len(clean_headers), len(values)))
            }
            if any(row.values()):
                rows.append(row)
        return clean_headers, rows
    finally:
        wb.close()


def propose_mapping(headers: list[str], source_type: str) -> dict:
    """Propose {original header: canonical field} for the operator to confirm.

    For a LinkedIn export this is the preset. For a generic sheet it is a
    heuristic guess — always shown for confirmation, never applied silently.
    """
    if source_type == SOURCE_LINKEDIN:
        return {h: LINKEDIN_PRESET[normalize_header(h)]
                for h in headers
                if normalize_header(h) in LINKEDIN_PRESET}

    mapping: dict[str, str] = {}
    taken: set[str] = set()
    for header in headers:
        norm = normalize_header(header)
        if not norm:
            continue
        for pattern, field in _HEURISTICS:
            if field in taken:
                continue
            if re.search(pattern, norm):
                mapping[header] = field
                taken.add(field)
                break
    return mapping


def is_linkedin_export(headers: list[str]) -> bool:
    """True when the headers look like LinkedIn's connections export."""
    norm = {normalize_header(h) for h in headers}
    return {"first name", "last name", "company"}.issubset(norm)


def validate_mapping(mapping: dict) -> list[str]:
    """Return a list of problems with a proposed mapping. Empty means usable."""
    problems = []
    fields = list(mapping.values())

    unknown = sorted(set(fields) - set(CANONICAL_FIELDS))
    if unknown:
        problems.append(f"Unknown target fields: {', '.join(unknown)}")

    duplicates = sorted({f for f in fields if fields.count(f) > 1})
    if duplicates:
        problems.append(
            f"Multiple columns mapped to the same field: {', '.join(duplicates)}"
        )

    # Hunter needs a name. Either a full name to split, or a first+last pair.
    has_name = "full_name" in fields or ("first_name" in fields and "last_name" in fields)
    if not has_name:
        problems.append(
            "Need a name column: map either 'full_name', or both "
            "'first_name' and 'last_name'"
        )

    # And it needs something to derive a domain from.
    if not ({"domain", "org_name", "email"} & set(fields)):
        problems.append(
            "Need a domain source: map 'domain', 'org_name', or 'email'"
        )
    return problems


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split a display name into (first, last) for Hunter's Email Finder.

    Handles "Last, First" as well as "First Last", strips common honorifics and
    suffixes, and keeps multi-word surnames intact.
    """
    name = re.sub(r"\s+", " ", (full_name or "").strip())
    if not name:
        return "", ""

    # Drop parenthetical asides: "Jane Doe (she/her)" or "Jane Doe (CFTC)".
    name = re.sub(r"\s*\([^)]*\)", "", name).strip()

    honorifics = {"mr", "mrs", "ms", "miss", "dr", "prof", "hon", "sen", "rep", "the"}
    suffixes = {"jr", "sr", "ii", "iii", "iv", "phd", "esq", "jd", "mba", "cfa"}

    # "Jane Doe, PhD" is a suffix, not "Last, First" — strip it before deciding.
    if "," in name:
        head, _, tail = name.rpartition(",")
        if tail.strip().rstrip(".").lower() in suffixes:
            name = head.strip()

    if "," in name:
        last, _, first = name.partition(",")
        first_parts = first.strip().split()
        return (first_parts[0] if first_parts else "", last.strip())

    parts = [p for p in name.split(" ") if p]

    while parts and parts[0].rstrip(".").lower() in honorifics:
        parts.pop(0)
    while parts and parts[-1].rstrip(".,").lower() in suffixes:
        parts.pop()

    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    # Drop a middle initial: "Jane Q. Doe" -> Jane / Doe
    if len(parts) > 2 and re.fullmatch(r"[A-Za-z]\.?", parts[1]):
        return parts[0], " ".join(parts[2:])
    return parts[0], " ".join(parts[1:])


def apply_mapping(row: dict, mapping: dict) -> dict:
    """Project one raw row onto canonical fields, filling names and domain.

    Returns a dict with every canonical field present (empty string when absent).
    """
    out = {f: "" for f in CANONICAL_FIELDS}
    for header, field in mapping.items():
        if field in out:
            out[field] = (row.get(header) or "").strip()

    # Derive the name pair Hunter needs.
    if not (out["first_name"] and out["last_name"]) and out["full_name"]:
        first, last = split_full_name(out["full_name"])
        out["first_name"] = out["first_name"] or first
        out["last_name"] = out["last_name"] or last
    if not out["full_name"]:
        out["full_name"] = " ".join(
            p for p in (out["first_name"], out["last_name"]) if p
        ).strip()

    # A domain in the sheet wins; otherwise take it from an email if present.
    out["domain"] = normalize_domain(out["domain"]) or domain_from_email(out["email"])
    return out


def normalize_domain(value: str) -> str:
    """Strip scheme, www, path, and port from anything domain-shaped."""
    text = (value or "").strip().lower()
    if not text:
        return ""
    if "@" in text:
        return domain_from_email(text)
    text = re.sub(r"^[a-z][a-z0-9+.-]*://", "", text)
    text = text.split("/")[0].split("?")[0].split(":")[0]
    text = text.removeprefix("www.")
    # A bare label with no dot is not a domain.
    if "." not in text or text.endswith("."):
        return ""
    if not re.fullmatch(r"[a-z0-9.-]+", text):
        return ""
    return text


def domain_from_email(email: str) -> str:
    """Domain part of an email, normalized. Empty when not an email."""
    text = (email or "").strip().lower()
    if "@" not in text:
        return ""
    domain = text.rsplit("@", 1)[1]
    domain = domain.split(">")[0].strip().strip(".")
    if "." not in domain:
        return ""
    return domain if re.fullmatch(r"[a-z0-9.-]+", domain) else ""


# Webmail domains are not employers: finding "someone at gmail.com" is
# meaningless, so rows that resolve to one are treated as having no domain.
FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "ymail.com",
        "hotmail.com",
        "outlook.com",
        "live.com",
        "msn.com",
        "aol.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "proton.me",
        "protonmail.com",
        "gmx.com",
        "mail.com",
        "zoho.com",
        "comcast.net",
        "verizon.net",
        "att.net",
    }
)


def is_free_email_domain(domain: str) -> bool:
    return (domain or "").strip().lower() in FREE_EMAIL_DOMAINS
