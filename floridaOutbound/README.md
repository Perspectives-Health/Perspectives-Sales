# Florida Outbound Map — Perspectives Health

Interactive map of behavioral health outreach targets for Eshan's trip Apr 13–18, 2026.

**What is this:** Perspectives Health is a VC-backed startup building AI to fight insurance denials in behavioral health. Eshan (founder) is doing in-person outreach in Central FL (Apr 14–15) and South FL / Boca area (Apr 16–18).

---

## Adding new leads (Origami AI CSV)

Full pipeline for a new batch of leads:

```bash
# 1. Export CSV from Origami AI, save to this folder

# For Origami AI exports (recommended — auto-extracts lat/lng, emails, ICP tier):
python3 workflowScripts/import-origami.py export-YYYY-MM-DD.csv

# For generic/other CSVs (flexible column matching, needs manual enrichment after):
python3 workflowScripts/import-csv.py leads.csv

# 2. For generic CSV: hand off to a Claude instance with this prompt:
#    "New companies were appended to companies.json with icp.tier=null and lat/lng=null.
#     For each: research exec team, geocode address, evaluate ICP tier (1/2/3),
#     research PE ownership. Update companies.json. README has schema and enum values."

# 3. Once enriched:
python3 workflowScripts/inject.py       # bake data into the map
# Refresh browser
```

**workflowScripts/import-origami.py** handles Origami AI's specific format: extracts lat/lng from the Raw Data JSON blob, uses confirmed emails, auto-assigns ICP tier from commercial insurance + levels of care signals, and merges people into existing companies without duplication.

**workflowScripts/import-csv.py** handles flexible generic CSVs (Company, Contact, Title, Email, Phone, LinkedIn, Website, City, State). New companies get flagged with `⚠ Not yet evaluated` so they're easy to find.

---

## Quick start

Open `florida-map.html` directly in any browser. No server needed.

After editing `companies.json`, run:
```bash
python3 workflowScripts/inject.py
```
Then refresh the browser tab.

---

## Files

| File | Purpose |
|------|---------|
| `florida-map.html` | The map — open directly in browser |
| `companies.json` | **Source of truth** — edit this, then run inject.py |
| `workflowScripts/inject.py` | Syncs companies.json → florida-map.html |
| `workflowScripts/import-origami.py` | Import Origami AI CSV exports |
| `workflowScripts/import-csv.py` | Import generic CSV leads |
| `outreach-tracker.md` | Original outreach log with sent messages |
| `enriched-contacts.md` | Full contact/exec sheet with route suggestions |
| `pe-research.md` | PE ownership deep-dive (in progress, another instance) |

---

## ICP (who we're targeting)

- CEO, Executive Director, COO, Owner at mid-size SUD + mental health orgs
- Must accept commercial insurance
- PE-backed orgs are high priority — under margin pressure, care about denial revenue
- UR Director is best internal champion (lives in the denial pain daily)
- CFO is strong at PE-backed orgs
- **Skip:** MAT-only, faith-based/no-insurance, single-location family medicine

**ICP tiers in data:**
- `tier: 1` — strong fit, prioritize
- `tier: 2` — good fit, worth the meeting
- `tier: 3` — flagged/skip (reason in `icp.flag`)

---

## companies.json schema

### Company-level fields
```json
{
  "id": "unique_snake_case_id",
  "name": "Company Name",
  "region": "central | south",
  "address": "full street address",
  "phone": "(xxx) xxx-xxxx | null",
  "website": "domain.com (no https)",
  "lat": 00.0000,
  "lng": -00.0000,
  "pe": {
    "backed": true | false,
    "firm": "Firm Name | null",
    "platform": "Platform/holding company name | null",
    "deal_partner": "Name (Title) | null",
    "notes": "deal history, amounts, context"
  },
  "icp": {
    "tier": 1 | 2 | 3,
    "flag": "reason string if flagged | null"
  },
  "notes": "internal context, strategy notes",
  "press": [{ "title": "...", "url": "...", "date": "YYYY-MM-DD" }]
}
```

### Person-level fields
```json
{
  "name": "Full Name",
  "credentials": "MBA, LCSW, etc. | null",
  "title": "Full job title",
  "role_type": "see valid values below",
  "email": "email@domain.com | null",
  "email_confidence": "see valid values below | null",
  "phone": "(xxx) xxx-xxxx | null",
  "linkedin": "full URL | null",
  "outreach": {
    "status": "see valid values below",
    "date": "YYYY-MM-DD | null",
    "channel": "email | linkedin | phone | text | null",
    "notes": "subject line, context, follow-up needed"
  },
  "connections": {
    "corey_jentry": "1st | 2nd | 3rd | null",
    "taylor_glenn": "1st | 2nd | 3rd | null"
  }
}
```

### Valid enum values

**`role_type`**
- `ceo` — CEO, Owner, Founder, President
- `coo` — COO, VP Operations
- `cfo` — CFO
- `ed` — Executive Director
- `clinical_leadership` — CCO, Clinical Director, Executive Clinical Director
- `ur_director` — Utilization Review Director (highest priority champion)
- `medical` — Medical Director, Psychiatrist, MD
- `director` — Director-level (ops, nursing, revenue cycle, etc.)
- `admissions` — Director/Coordinator of Admissions
- `marketing` — CMO, Marketing, Business Development

**`email_confidence`**
- `confirmed` — verified working address
- `zoominfo` — sourced from ZoomInfo (partially redacted but pattern confirmed)
- `inferred` — derived from company email pattern, not verified
- `public` — listed publicly on website

**`outreach.status`**
- `booked` — meeting confirmed
- `sent` — outreach sent, awaiting response
- `no_response` — sent, no reply, should follow up
- `not_contacted` — haven't reached out yet
- `skipped` — intentionally not contacting (with reason in notes)

---

## What's pending / still to do

- [ ] **PE research** — another instance is working on `pe-research.md`. When done, update `pe.backed`, `pe.firm`, `pe.deal_partner`, `pe.notes` in companies.json for any newly confirmed PE-backed orgs, then run `inject.py`
- [ ] **Press finds** — add to each company's `press` array
- [ ] **LinkedIn connections** — Aneesh will manually check. Fill in `connections.corey_jentry` and `connections.taylor_glenn` with `"1st"`, `"2nd"`, or `"3rd"` per person
- [ ] **Email verification** — inferred emails are unverified. Upgrade `email_confidence` to `confirmed` if verified

---

## Trip route (for context)

**Mon Apr 14:** Lifeskills (Orlando) — Klay Weaver lunch noon  
**Tue Apr 15:** DeLand Treatment Solutions — Zach Miller lunch  
**Wed Apr 16 → Fri Apr 18:** South FL (Boca area) — driving down  
- Futures Recovery (Tequesta, northernmost)  
- HEAL (West Palm Beach)  
- Lighthouse + Boca Recovery (Boynton/Boca)  
- Olympic + Renaissance (Lantana — same road, 3 min apart)  
- JC's Recovery (Hollywood, southernmost)
