#!/usr/bin/env python3
"""
Import Origami AI CSV export into companies.json.

Usage:
    python3 import-origami.py export-2026-04-08.csv

Handles Origami's specific column format:
  - Company, Website, Location, Executive, Executive/Title, Executive/Linkedin url
  - Email (confirmed by Origami)
  - Raw Data (JSON blob with lat/lng, phones, street_address)
  - Treatment Profile/Is iop only, Treatment Profile/Levels of care
  - Commercial Insurance (true/false)
  - Fit Score

Merges new people into existing companies, adds new companies as skeletons.
Auto-assigns ICP tier from available signals.
"""

import csv, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent.parent
JSON = HERE / "companies.json"

CENTRAL_CITIES = {
    "orlando", "deland", "de land", "cocoa", "kissimmee", "sanford",
    "leesburg", "ocala", "gainesville", "daytona", "edgewater", "altoona",
    "clermont", "lakeland", "winter haven", "altamonte springs", "maitland",
    "longwood", "oviedo", "winter park", "apopka", "deltona", "palm coast",
    "st. augustine", "saint augustine", "jacksonville", "gainesville", "tampa",
    "clearwater", "st. petersburg", "saint petersburg", "sarasota", "bradenton",
}

SOUTH_CITIES = {
    "miami", "fort lauderdale", "boca raton", "west palm beach", "palm beach",
    "boynton beach", "delray beach", "lantana", "lake worth", "tequesta",
    "jupiter", "hollywood", "hialeah", "pompano beach", "deerfield beach",
    "coral springs", "plantation", "hallandale", "aventura", "north miami",
    "pembroke pines", "miramar", "weston", "davie", "sunrise", "margate",
    "coconut creek", "tamarac", "lauderhill", "oakland park", "wilton manors",
    "palm beach gardens", "riviera beach", "singer island", "greenacres",
    "wellington", "royal palm beach", "loxahatchee", "stuart", "port st. lucie",
}


def infer_region(city):
    c = (city or "").lower().strip()
    for kw in SOUTH_CITIES:
        if kw in c:
            return "south"
    for kw in CENTRAL_CITIES:
        if kw in c:
            return "central"
    return "south"  # default for FL


def infer_role_type(title):
    t = (title or "").lower()
    if any(x in t for x in ["coo", "chief operating"]):
        return "coo"
    if any(x in t for x in ["cfo", "chief financial"]):
        return "cfo"
    if any(x in t for x in ["clinical director", "cco", "chief clinical"]):
        return "clinical_leadership"
    if any(x in t for x in ["utilization", "ur director", "ur manager"]):
        return "ur_director"
    if any(x in t for x in ["medical director", " md", " do", "psychiatrist"]):
        return "medical"
    if any(x in t for x in ["executive director"]):
        return "ed"
    if any(x in t for x in ["director"]):
        return "director"
    if any(x in t for x in ["admissions"]):
        return "admissions"
    if any(x in t for x in ["marketing", "business development", "biz dev"]):
        return "marketing"
    return "ceo"


def icp_tier(row, raw):
    """Auto-assign ICP tier from Origami signals."""
    commercial = (row.get("Commercial Insurance") or "").lower() == "true"
    iop_only = (row.get("Treatment Profile/Is iop only") or "").lower() == "true"
    levels_raw = row.get("Treatment Profile/Levels of care") or ""
    try:
        levels = json.loads(levels_raw) if levels_raw else []
    except Exception:
        levels = []
    fit = int(row.get("Fit Score") or 0)

    # Tier 3: disqualifying signals
    if not commercial:
        return 3, "Does not accept commercial insurance"
    if iop_only:
        return 3, "IOP-only — lower denial volume"

    # Check for residential / full continuum
    has_residential = any("residential" in l.lower() or "inpatient" in l.lower() or "detox" in l.lower() for l in levels)

    if has_residential and fit >= 70:
        return 1, None
    if fit >= 60 or has_residential:
        return 2, None
    return 2, None


def make_phone(raw):
    """Extract best phone from raw data blob."""
    biz = raw.get("business_phones") or []
    store = raw.get("store_phones") or []
    for p in biz + store:
        if p:
            # Format as (xxx) xxx-xxxx
            digits = re.sub(r"\D", "", p)
            if len(digits) == 11 and digits[0] == "1":
                digits = digits[1:]
            if len(digits) == 10:
                return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return None


def make_address(raw, location_str):
    street = raw.get("street_address") or ""
    city = raw.get("city") or ""
    state = raw.get("state") or ""
    zipcode = raw.get("zipcode") or ""
    if street and city:
        parts = [p for p in [street, city, state, zipcode] if p]
        return ", ".join(parts)
    return location_str or None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "export-2026-04-08.csv"
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    with open(JSON) as f:
        companies = json.load(f)

    existing_by_name = {c["name"].lower(): c for c in companies}

    added, merged_people, updated_fields = 0, 0, 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group by company (multiple execs per company possible)
    groups = {}
    for row in rows:
        co = (row.get("Company") or "").strip()
        if not co:
            continue
        if co not in groups:
            groups[co] = {"rows": []}
        groups[co]["rows"].append(row)

    for co_name, data in groups.items():
        first_row = data["rows"][0]
        raw_str = first_row.get("Raw Data") or "{}"
        try:
            raw = json.loads(raw_str)
        except Exception:
            raw = {}

        lat = raw.get("latitude")
        lng = raw.get("longitude")
        address = make_address(raw, first_row.get("Location"))
        phone = make_phone(raw)
        website = (first_row.get("Website") or "").replace("https://", "").replace("http://", "").rstrip("/")
        city = raw.get("city") or ""
        region = infer_region(city)

        tier, flag = icp_tier(first_row, raw)

        # Build people list
        people = []
        for row in data["rows"]:
            exec_name = (row.get("Executive") or "").strip() or None
            if not exec_name:
                continue
            title = (row.get("Executive/Title") or "").strip() or None
            linkedin = (row.get("Executive/Linkedin url") or "").strip() or None
            email = (row.get("Email") or "").strip() or None
            people.append({
                "name": exec_name,
                "credentials": None,
                "title": title,
                "role_type": infer_role_type(title),
                "email": email,
                "email_confidence": "confirmed" if email else None,
                "phone": None,
                "linkedin": linkedin,
                "outreach": {"status": "not_contacted", "date": None, "channel": None, "notes": None},
                "connections": {"corey_jentry": None, "taylor_glenn": None},
            })

        key = co_name.lower()
        if key in existing_by_name:
            existing = existing_by_name[key]
            # Merge: update lat/lng if missing, update phone if missing, merge people
            if not existing.get("lat") and lat:
                existing["lat"] = lat
                existing["lng"] = lng
                updated_fields += 1
            if not existing.get("phone") and phone:
                existing["phone"] = phone
                updated_fields += 1
            if not existing.get("address") and address:
                existing["address"] = address
                updated_fields += 1
            if not existing.get("website") and website:
                existing["website"] = website
                updated_fields += 1

            existing_person_names = {p["name"].lower() for p in existing.get("people", [])}
            for p in people:
                if p["name"] and p["name"].lower() not in existing_person_names:
                    existing.setdefault("people", []).append(p)
                    existing_person_names.add(p["name"].lower())
                    merged_people += 1
                    print(f"  + Merged person into {co_name}: {p['name']}")
            print(f"  ~ Updated existing: {co_name}")
        else:
            # New company
            entry = {
                "id": slug(co_name),
                "name": co_name,
                "region": region,
                "address": address,
                "phone": phone,
                "website": website,
                "lat": lat,
                "lng": lng,
                "pe": {
                    "backed": False,
                    "firm": None,
                    "platform": None,
                    "deal_partner": None,
                    "notes": "⚠ Not yet researched",
                },
                "icp": {"tier": tier, "flag": flag},
                "notes": f"Imported from Origami AI (Fit Score: {first_row.get('Fit Score')}). Levels of care: {first_row.get('Treatment Profile/Levels of care', 'unknown')}",
                "press": [],
                "people": people,
            }
            companies.append(entry)
            existing_by_name[key] = entry
            added += 1
            print(f"  + Added: {co_name} (tier {tier}, {len(people)} people)")

    with open(JSON, "w") as f:
        json.dump(companies, f, indent=2)

    print(f"\n✓ Done: {added} new companies added, {merged_people} people merged into existing, {updated_fields} fields updated")
    print(f"Total companies: {len(companies)}")
    print("Next: run python3 workflowScripts/inject.py")


if __name__ == "__main__":
    main()
