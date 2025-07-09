# scripts/data_gen.py
# -----------------------------------------------------------
# Synthetic medical-charge data for Alabama visualisation demo
# Only standard-library + pandas + json are used
# -----------------------------------------------------------
import os, json, random
from pathlib import Path
from datetime import date, timedelta
import pandas as pd

# 0 — folders -------------------------------------------------
BASE  = Path(__file__).parents[1]          # project root (UUID folder)
DATA  = BASE / "data"
DATA.mkdir(exist_ok=True) # Removed parents=True as it's not needed for a single directory

# 1 — reference lists ----------------------------------------
random.seed(42)

cities = [  # name, lat, lon  (all inside AL)
    ("Birmingham",      33.5207, -86.8025),
    ("Montgomery",      32.3792, -86.3077),
    ("Mobile",          30.6954, -88.0399),
    ("Huntsville",      34.7304, -86.5861),
    ("Tuscaloosa",      33.2098, -87.5692),
    ("Dothan",          31.2232, -85.3905),
    ("Auburn",          32.6099, -85.4808),
    ("Decatur",         34.6059, -86.9833),
    ("Gadsden",         34.0143, -86.0066),
    ("Florence",        34.7998, -87.6773)
]

payers       = ["Medicare", "Medicaid", "Private", "Self-Pay"]
proc_cats    = ["Cardiology", "Orthopedics", "Oncology",
                "Diagnostic", "General Surgery"]
sub_by_cat   = {
    "Cardiology"      : ["Stent", "CABG", "Angiogram"],
    "Orthopedics"     : ["Knee Replacement", "Hip Replacement", "Arthroscopy"],
    "Oncology"        : ["Chemo Session", "Radiation", "Immunotherapy"],
    "Diagnostic"      : ["MRI", "CT Scan", "Ultrasound"],
    "General Surgery" : ["Appendectomy", "Cholecystectomy", "Hernia Repair"]
}

# generate 35 providers (3-4 per listed city)
providers = []
prov_id   = 1
for city, lat, lon in cities:
    for _ in range(random.randint(3,4)):
        providers.append({
            "provider_id"  : prov_id,
            "provider_name": f"{city[:3].upper()}-Med {prov_id}",
            "city"         : city,
            "lat"          : round(lat  + random.uniform(-0.12, 0.12), 4),
            "lon"          : round(lon  + random.uniform(-0.12, 0.12), 4)
        })
        prov_id += 1
prov_df = pd.DataFrame(providers)
prov_df.to_csv(DATA / "provider_locations.csv", index=False)

# 2 — row-level charge data ----------------------------------
start_date = date(2023, 1, 1)
months     = [start_date + timedelta(days=30*i) for i in range(12)]

records = []
for m in months:
    month_str = m.strftime("%Y-%m")
    for p in providers:
        # pick 4-8 procedures for this provider & month
        sampled_cats = random.sample(proc_cats, k=random.randint(3,5))
        for cat in sampled_cats:
            sub_proc = random.choice(sub_by_cat[cat])
            for _ in range(random.randint(8,15)):      # individual cases
                payer   = random.choices(payers, weights=[0.35,0.25,0.3,0.1])[0]
                base    = random.uniform(2_000, 25_000)
                # oncology generally more expensive
                if cat == "Oncology":
                    base *= 1.8
                # private payer prices tend to be higher
                if payer == "Private":
                    base *= 1.15
                charge  = round(base, 2)

                records.append([
                    p["provider_id"], p["provider_name"], p["city"],
                    p["lat"], p["lon"],
                    payer, cat, sub_proc,
                    month_str, charge
                ])

cols = ["provider_id","provider_name","city","lat","lon",
        "payer_type","procedure_category","procedure_sub",
        "month","charge_amount"]
charges_df = pd.DataFrame(records, columns=cols)
charges_df.to_csv(DATA / "charges.csv", index=False)

# 3 — headline KPI -------------------------------------------
avg_charge = round(charges_df["charge_amount"].mean(), 2)
with open(DATA / "kpi.json", "w") as f:
    json.dump({"average_charge": avg_charge}, f)

print("✅  Data generation complete — files in /data")