#!/usr/bin/env python3
"""
Convert an Origami AI CSV export into companies.json skeleton entries.

Usage:
    python3 import-csv.py leads.csv

Appends new companies to companies.json (skips any company name that already exists).
After running, a Claude instance needs to fill in:
  - lat/lng (geocode from address)
  - full people array (research exec team)
  - pe fields (PE research)
  - icp.tier (ICP evaluation)

Expected CSV columns (flexible — script tries common variants):
  Company / Company Name / Organization
  Contact / First Name + Last Name / Full Name
  Title / Role / Job Title
  Email / Email Address
  Phone / Phone Number
  LinkedIn / LinkedIn URL / Profile URL
  Website / Domain / URL
  City / Location
  State
  Notes / Description
"""

import csv, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
JSON = HERE / "companies.json"

# ── Column name aliases ──
ALIASES = {
    "company":   ["company", "company name", "organization", "org", "account"],
    "name":      ["full name", "contact", "name", "contact name"],
    "first":     ["first name", "first"],
    "last":      ["last name", "last"],
    "title":     ["title", "job title", "role", "position"],
    "email":     ["email", "email address", "work email"],
    "phone":     ["phone", "phone number", "mobile", "direct phone"],
    "linkedin":  ["linkedin", "linkedin url", "profile url", "li url"],
    "website":   ["website", "domain", "url", "web"],
    "city":      ["city", "location"],
    "state":     ["state"],
    "notes":     ["notes", "description", "comments"],
    "region":    ["region", "territory"],
}

def match_col(headers, field):
    for h in headers:
        if h.lower().strip() in ALIASES.get(field, []):
            return h
    return None

def normalize(val):
    return (val or "").strip() or None

def infer_region(city, state):
    central_cities = {"orlando", "deland", "deland", "cocoa", "kissimmee", "sanford",
                      "leesburg", "ocala", "gainesville", "daytona", "edgewater", "altoona"}
    south_cities = {"miami", "fort lauderdale", "boca raton", "west palm beach", "palm beach",
                    "boynton beach", "delray beach", "lantana", "lake worth", "tequesta",
                    "jupiter", "hollywood", "hialeah", "pompano beach", "deerfield beach",
                    "coral springs", "plantation"}
    c = (city or "").lower().strip()
    for kw in central_cities:
        if kw in c:
            return "central"
    for kw in south_cities:
        if kw in c:
            return "south"
    return "south"  # default for FL outbound

def make_skeleton(company_name, person, region):
    role_type = "ceo"
    title_lower = (person.get("title") or "").lower()
    if any(x in title_lower for x in ["coo", "chief operating"]):
        role_type = "coo"
    elif any(x in title_lower for x in ["cfo", "chief financial"]):
        role_type = "cfo"
    elif any(x in title_lower for x in ["clinical director", "cco", "chief clinical"]):
        role_type = "clinical_leadership"
    elif any(x in title_lower for x in ["utilization", "ur director", "ur manager"]):
        role_type = "ur_director"
    elif any(x in title_lower for x in ["medical director", " md", " do"]):
        role_type = "medical"
    elif any(x in title_lower for x in ["executive director", " ed "]):
        role_type = "ed"
    elif any(x in title_lower for x in ["director"]):
        role_type = "director"
    elif any(x in title_lower for x in ["admissions"]):
        role_type = "admissions"
    elif any(x in title_lower for x in ["marketing", "business development", "biz dev"]):
        role_type = "marketing"

    person_entry = {
        "name": person.get("name"),
        "credentials": None,
        "title": person.get("title"),
        "role_type": role_type,
        "email": person.get("email"),
        "email_confidence": "confirmed" if person.get("email") else None,
        "phone": person.get("phone"),
        "linkedin": person.get("linkedin"),
        "outreach": {"status": "not_contacted", "date": None, "channel": None, "notes": person.get("notes")},
        "connections": {"corey_jentry": None, "taylor_glenn": None}
    }

    slug = re.sub(r"[^a-z0-9]+", "_", company_name.lower()).strip("_")

    return {
        "id": slug,
        "name": company_name,
        "region": region,
        "address": person.get("address"),          # ⚠ needs geocoding
        "phone": person.get("company_phone"),
        "website": person.get("website"),
        "lat": None,                                # ⚠ needs geocoding
        "lng": None,                                # ⚠ needs geocoding
        "pe": {
            "backed": False,
            "firm": None,
            "platform": None,
            "deal_partner": None,
            "notes": "⚠ Not yet researched"
        },
        "icp": {"tier": None, "flag": "⚠ Not yet evaluated — needs ICP review"},
        "notes": "⚠ Imported from Origami CSV — needs full enrichment (execs, PE, address, ICP tier)",
        "press": [],
        "people": [person_entry] if person_entry["name"] else []
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 import-csv.py leads.csv")
        sys.exit(1)

    csv_path = Path(sys.argv[1])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    with open(JSON) as f:
        companies = json.load(f)

    existing_names = {c["name"].lower() for c in companies}
    added, skipped, merged = 0, 0, 0

    # Group rows by company
    company_groups = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []

        col = {field: match_col(headers, field) for field in ALIASES}

        for row in reader:
            def get(field):
                c = col.get(field)
                return normalize(row.get(c, "")) if c else None

            # Build full name
            name = get("name") or f"{get('first') or ''} {get('last') or ''}".strip() or None

            # Company
            co_name = get("company")
            if not co_name:
                continue

            city = get("city")
            state = get("state")
            region = infer_region(city, state)

            address_parts = [p for p in [city, state] if p]
            address = ", ".join(address_parts) if address_parts else None

            person = {
                "name": name,
                "title": get("title"),
                "email": get("email"),
                "phone": get("phone"),
                "linkedin": get("linkedin"),
                "notes": get("notes"),
                "address": address,
                "website": get("website"),
                "company_phone": None,
            }

            company_groups.setdefault(co_name, {"region": region, "people": []})
            if name:
                company_groups[co_name]["people"].append(person)

    for co_name, data in company_groups.items():
        if co_name.lower() in existing_names:
            # Merge new people into existing company
            existing = next(c for c in companies if c["name"].lower() == co_name.lower())
            existing_person_names = {p["name"].lower() for p in existing["people"]}
            for person in data["people"]:
                if person["name"] and person["name"].lower() not in existing_person_names:
                    skeleton = make_skeleton(co_name, person, data["region"])
                    existing["people"].extend(skeleton["people"])
                    merged += 1
            skipped += 1
            print(f"  ~ Merged into existing: {co_name}")
        else:
            skeleton = make_skeleton(co_name, data["people"][0] if data["people"] else {}, data["region"])
            # Add additional people
            for person in data["people"][1:]:
                extra = make_skeleton(co_name, person, data["region"])
                skeleton["people"].extend(extra["people"])
            companies.append(skeleton)
            existing_names.add(co_name.lower())
            added += 1
            print(f"  + Added: {co_name} ({len(skeleton['people'])} people)")

    with open(JSON, "w") as f:
        json.dump(companies, f, indent=2)

    print(f"\n✓ Done: {added} added, {skipped} already existed ({merged} people merged), {len(companies)} total companies")
    print("Next: fill in lat/lng, ICP tier, PE research, then run: python3 inject.py")

if __name__ == "__main__":
    main()
