"""Look up CEO emails via the Hunter.io Email Finder API.

Reads the API key from the HUNTER_API_KEY environment variable (or the first
CLI argument). Writes results to hunter_results.json at the repository root.
The key is never written to any file or log.

Usage:
    HUNTER_API_KEY=... python3 scripts/hunter_lookup.py
"""
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API_KEY = os.environ.get("HUNTER_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not API_KEY:
    sys.exit("Set HUNTER_API_KEY or pass the key as the first argument.")

CA_BUNDLE = "/root/.ccr/ca-bundle.crt"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (row_id, company, domain, person name) — rows match the CEO Map sheet of
# AI_CEO_Outreach_Priority_Map_20260910.xlsx; QTS has co-CEOs, hence two rows.
TARGETS = [
    (1, "NVIDIA", "nvidia.com", "Jensen Huang"),
    (2, "AMD", "amd.com", "Lisa Su"),
    (3, "CoreWeave", "coreweave.com", "Mike Intrator"),
    (4, "Crusoe", "crusoe.ai", "Chase Lochmiller"),
    (5, "QTS", "qtsdatacenters.com", "Tag Greason"),
    (5, "QTS", "qtsdatacenters.com", "David Robey"),
    (6, "GE Vernova", "gevernova.com", "Scott Strazik"),
    (7, "Eaton", "eaton.com", "Paulo Ruiz"),
    (8, "AEP", "aep.com", "Bill Fehrman"),
    (9, "Microsoft", "microsoft.com", "Satya Nadella"),
    (10, "OpenAI", "openai.com", "Sam Altman"),
    (11, "Anthropic", "anthropic.com", "Dario Amodei"),
    (12, "Databricks", "databricks.com", "Ali Ghodsi"),
    (13, "AWS", "amazon.com", "Matt Garman"),
    (14, "Alphabet / Google", "google.com", "Sundar Pichai"),
    (15, "Oracle", "oracle.com", "Clay Magouyrk"),
    (16, "Micron", "micron.com", "Sanjay Mehrotra"),
    (17, "TSMC", "tsmc.com", "C.C. Wei"),
    (18, "Broadcom", "broadcom.com", "Hock Tan"),
    (19, "Constellation", "constellationenergy.com", "Joseph Dominguez"),
    (20, "Vertiv", "vertiv.com", "Giordano Albertazzi"),
    (21, "Quanta Services", "quantaservices.com", "Duke Austin"),
    (22, "Digital Realty", "digitalrealty.com", "Andy Power"),
]

ctx = ssl.create_default_context(
    cafile=CA_BUNDLE if os.path.exists(CA_BUNDLE) else None
)


def find_email(domain: str, full_name: str) -> dict:
    params = urllib.parse.urlencode(
        {"domain": domain, "full_name": full_name, "api_key": API_KEY}
    )
    url = f"https://api.hunter.io/v2/email-finder?{params}"
    try:
        with urllib.request.urlopen(url, context=ctx, timeout=30) as resp:
            body = json.load(resp)
        d = body.get("data", {})
        return {
            "email": d.get("email"),
            "score": d.get("score"),
            "position": d.get("position"),
            "verification": (d.get("verification") or {}).get("status"),
            "error": None,
        }
    except urllib.error.HTTPError as e:
        try:
            err_body = json.load(e)
            msg = "; ".join(x.get("details", "") for x in err_body.get("errors", []))
        except Exception:
            msg = ""
        return {"email": None, "score": None, "position": None,
                "verification": None, "error": f"HTTP {e.code}: {msg}".strip()}
    except Exception as e:
        return {"email": None, "score": None, "position": None,
                "verification": None, "error": str(e)}


def main() -> None:
    results = []
    for row_id, company, domain, name in TARGETS:
        r = find_email(domain, name)
        r.update({"id": row_id, "company": company, "domain": domain, "name": name})
        results.append(r)
        status = r["error"] or f"{r['email']} (score {r['score']}, {r['verification']})"
        print(f"[{row_id}] {company} / {name}: {status}", flush=True)
        time.sleep(1.2)

    out = os.path.join(REPO_ROOT, "hunter_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} results to {out}")


if __name__ == "__main__":
    main()
