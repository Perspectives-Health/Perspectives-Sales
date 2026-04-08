#!/usr/bin/env python3
"""Inject companies.json into florida-map.html. Run after any data update."""
import json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
JSON = HERE / "companies.json"
HTML = HERE / "florida-map.html"

with open(JSON) as f:
    data = json.load(f)

with open(HTML) as f:
    html = f.read()

new_decl = "const COMPANIES = " + json.dumps(data, separators=(",", ":")) + ";"
html = re.sub(r"const COMPANIES = \[.*?\];", lambda m: new_decl, html, flags=re.DOTALL)

with open(HTML, "w") as f:
    f.write(html)

print(f"✓ Injected {len(data)} companies into florida-map.html")
