"""Generate a 50-account test territory that exercises the coaching logic.

Today = 2026-04-18. Dataset is shaped to hit every branch of the hiking trail:

  * Red Zone fires (renewing 0-120 days with missing Open Opp / ESA / Notes)
  * Red Zone healthy (in good shape, shouldn't be flagged)
  * Strategy Zone current-year (May/Jun/Jul 2026 top-ARR)
  * Strategy Zone future anniversaries (May/Jun/Jul 2027-2029)
  * Mid-term reviews (Dec 2025 renewals)
  * Healthy baseline across other months
"""

from pathlib import Path

import pandas as pd

COLUMNS = [
    "Brand",
    "Account Owner",
    "Account Name",
    "Customer Renewal Date",
    "Customer Success Manager",
    "CR Customer ID",
    "Active Subscriptions ARR Rollup",
    "ESA Consultant",
    "Billing City",
    "Billing State",
    "Employees",
    "Type",
    "Price Increase %",
    "Open Opp?",
    "Assurance",
    "Invoice",
    "Travel",
    "Payments",
    "Notes",
]

rows = [
    # ----- Red Zone fires (0-120 days, problematic) -----
    ("Chrome River", "Sarah Chen", "Morrison Logistics Group", "2026-05-12", "", "CR-10023", 412000, "", "Atlanta", "GA", 1800, "Enterprise", 8, "N", "N", "Y", "N", "N", ""),
    ("Chrome River", "Sarah Chen", "Vega Pharmaceuticals", "2026-06-03", "Tom Bradshaw", "CR-10087", 680000, "", "Boston", "MA", 2400, "Enterprise", 15, "N", "N", "N", "N", "N", ""),
    ("Certify", "Sarah Chen", "Redline Manufacturing Co", "2026-07-22", "Priya Patel", "CR-10145", 295000, "Jordan Nakamura", "Cleveland", "OH", 950, "Mid-Market", 10, "N", "Y", "N", "N", "N", ""),
    ("Chrome River", "Sarah Chen", "Bluestone Financial", "2026-06-15", "", "CR-10198", 890000, "", "Charlotte", "NC", 3100, "Enterprise", 12, "N", "Y", "Y", "N", "N", "Primary contact left in Feb, new VP Finance is Amanda Reyes — haven't connected yet"),
    ("Certify", "Sarah Chen", "Coastal Systems Inc", "2026-05-28", "Kevin Wu", "CR-10234", 155000, "", "Tampa", "FL", 420, "Mid-Market", 7, "Y", "N", "Y", "N", "N", ""),
    ("Chrome River", "Sarah Chen", "Hemlock Industries", "2026-07-05", "", "CR-10289", 225000, "", "Pittsburgh", "PA", 680, "Mid-Market", 9, "", "N", "Y", "N", "N", ""),

    # ----- Red Zone healthy -----
    ("Chrome River", "Sarah Chen", "Parkway Dynamics", "2026-05-20", "Tom Bradshaw", "CR-10312", 340000, "Jordan Nakamura", "Denver", "CO", 1100, "Enterprise", 8, "Y", "Y", "Y", "N", "Y", "Renewal meeting booked for 5/6, champion is still CFO"),
    ("Chrome River", "Sarah Chen", "Meridian Holdings", "2026-06-10", "Priya Patel", "CR-10345", 560000, "Amanda Foley", "Chicago", "IL", 1950, "Enterprise", 10, "Working", "Y", "Y", "Y", "N", "In negotiations on Payments add-on, expecting close by 5/30"),
    ("Certify", "Sarah Chen", "Silvermark LLC", "2026-07-15", "Kevin Wu", "CR-10378", 180000, "Jordan Nakamura", "Portland", "OR", 380, "Mid-Market", 6, "Y", "Y", "Y", "N", "N", "Stable account, no surprises expected"),
    ("Chrome River", "Sarah Chen", "Thornfield Capital", "2026-08-04", "Tom Bradshaw", "CR-10401", 720000, "Ethan Vasquez", "New York", "NY", 2800, "Enterprise", 11, "Working", "Y", "Y", "Y", "N", "Strong champion, exploring Payments expansion"),
    ("Certify", "Sarah Chen", "Apex Freight", "2026-04-30", "Kevin Wu", "CR-10420", 120000, "Jordan Nakamura", "Memphis", "TN", 290, "Mid-Market", 5, "Y", "Y", "N", "N", "N", "Quick renewal expected, happy customer"),

    # ----- Strategy Zone future anniversaries (May/Jun/Jul 2027-2029) -----
    ("Chrome River", "Sarah Chen", "Ironwood Technologies", "2027-05-18", "Tom Bradshaw", "CR-10501", 1200000, "Amanda Foley", "Austin", "TX", 4200, "Enterprise", 10, "Y", "N", "Y", "N", "Y", "Big anchor account — CFO loves us"),
    ("Chrome River", "Sarah Chen", "Northstar Aerospace", "2027-06-22", "Priya Patel", "CR-10534", 850000, "", "Seattle", "WA", 2600, "Enterprise", 8, "Y", "Y", "Y", "Y", "N", "Watch for consolidation talk — heard they're reviewing T&E stack"),
    ("Certify", "Sarah Chen", "Blackwood Consulting", "2027-07-09", "Kevin Wu", "CR-10567", 420000, "Jordan Nakamura", "Washington", "DC", 1400, "Enterprise", 12, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Greenfield Solutions", "2028-05-04", "Tom Bradshaw", "CR-10612", 680000, "Ethan Vasquez", "San Francisco", "CA", 2100, "Enterprise", 9, "Y", "N", "N", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Stonebridge Partners", "2028-06-17", "Priya Patel", "CR-10645", 520000, "Amanda Foley", "Boston", "MA", 1700, "Enterprise", 7, "Y", "Y", "Y", "N", "N", ""),
    ("Certify", "Sarah Chen", "Harborline Shipping", "2028-07-11", "Kevin Wu", "CR-10678", 310000, "Jordan Nakamura", "Long Beach", "CA", 890, "Mid-Market", 10, "Y", "N", "Y", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Westpoint Analytics", "2029-05-20", "Kevin Wu", "CR-10712", 230000, "Nina Delgado", "Raleigh", "NC", 620, "Mid-Market", 8, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Falcon Electric", "2029-06-03", "Priya Patel", "CR-10745", 475000, "Amanda Foley", "Phoenix", "AZ", 1550, "Enterprise", 11, "Y", "N", "Y", "N", "N", ""),
    ("Chrome River", "Sarah Chen", "Ridgeview Health", "2029-07-25", "Tom Bradshaw", "CR-10778", 390000, "Ethan Vasquez", "Nashville", "TN", 1280, "Enterprise", 9, "Y", "Y", "N", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Pinnacle Engineering", "2027-05-28", "Tom Bradshaw", "CR-10812", 1500000, "Amanda Foley", "Houston", "TX", 5100, "Enterprise", 12, "Working", "N", "Y", "Y", "Y", "Whale account, needs careful handling"),
    ("Certify", "Sarah Chen", "Cedarwood Labs", "2028-06-28", "", "CR-10845", 275000, "", "Cambridge", "MA", 720, "Mid-Market", 8, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Ashford Retail Group", "2029-07-14", "Priya Patel", "CR-10878", 920000, "Ethan Vasquez", "Dallas", "TX", 3400, "Enterprise", 10, "Y", "Y", "N", "Y", "N", ""),
    ("Chrome River", "Sarah Chen", "Charon Robotics", "2027-06-14", "Tom Bradshaw", "CR-10912", 1800000, "Amanda Foley", "San Jose", "CA", 6200, "Enterprise", 15, "Y", "N", "Y", "N", "N", "Largest account in territory"),

    # ----- Mid-term reviews (Dec 2025 renewals = 4 months ago) -----
    ("Chrome River", "Sarah Chen", "Summit Precision", "2025-12-05", "Tom Bradshaw", "CR-11001", 780000, "Amanda Foley", "Minneapolis", "MN", 2500, "Enterprise", 8, "Y", "Y", "Y", "N", "Y", "CFO mentioned EU expansion Q3 2026, wanted to revisit international T&E coverage"),
    ("Chrome River", "Sarah Chen", "Foxfire Digital", "2025-12-14", "Priya Patel", "CR-11034", 520000, "Ethan Vasquez", "Los Angeles", "CA", 1700, "Enterprise", 9, "Y", "N", "Y", "Y", "Y", "New CFO starting Jan 2026, relationship is with old CFO — re-engage"),
    ("Chrome River", "Sarah Chen", "Halcyon Biotech", "2025-12-22", "Kevin Wu", "CR-11067", 1100000, "", "San Diego", "CA", 3700, "Enterprise", 10, "Y", "N", "Y", "Y", "N", "Re-evaluating their finance stack for clinical trials expansion, asked for follow-up in Q2"),
    ("Certify", "Sarah Chen", "Tanager Logistics", "2025-12-08", "Tom Bradshaw", "CR-11098", 340000, "Jordan Nakamura", "Kansas City", "MO", 920, "Mid-Market", 6, "Y", "Y", "Y", "Y", "Y", "Full product penetration, very happy"),
    ("Chrome River", "Sarah Chen", "Whitestone Energy", "2025-12-19", "Priya Patel", "CR-11132", 445000, "Amanda Foley", "Tulsa", "OK", 1450, "Enterprise", 7, "Y", "Y", "Y", "N", "N", "Budget freeze through Q1 2026 but CFO said revisit in April"),
    ("Certify", "Sarah Chen", "Brighton Foods", "2025-12-02", "", "CR-11165", 230000, "", "St. Louis", "MO", 640, "Mid-Market", 8, "Y", "Y", "N", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Cornerstone Insurance", "2025-12-28", "Tom Bradshaw", "CR-11198", 610000, "Ethan Vasquez", "Hartford", "CT", 2000, "Enterprise", 8, "Y", "Y", "Y", "Y", "N", "They asked about Concur alternatives during renewal — wanted a Q2 check-in on how we compare"),
    ("Certify", "Sarah Chen", "Finnegan Brewery", "2025-12-16", "Kevin Wu", "CR-11220", 175000, "", "Milwaukee", "WI", 380, "Mid-Market", 5, "Y", "Y", "N", "Y", "Y", ""),

    # ----- Healthy baseline / other months -----
    ("Chrome River", "Sarah Chen", "Diamondback Oil", "2026-09-12", "Priya Patel", "CR-11301", 520000, "Amanda Foley", "Oklahoma City", "OK", 1600, "Enterprise", 8, "Y", "Y", "Y", "Y", "Y", "Full penetration, QBR in Aug"),
    ("Certify", "Sarah Chen", "Evergreen Materials", "2026-10-05", "Kevin Wu", "CR-11334", 180000, "Nina Delgado", "Portland", "OR", 450, "Mid-Market", 7, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Gatewood Hospitality", "2026-11-20", "Tom Bradshaw", "CR-11367", 730000, "Ethan Vasquez", "Las Vegas", "NV", 2400, "Enterprise", 9, "Y", "Y", "Y", "Y", "Y", "Strong champion, multi-year renewal likely"),
    ("Chrome River", "Sarah Chen", "Hollowpark Media", "2026-12-08", "Priya Patel", "CR-11401", 290000, "Jordan Nakamura", "New York", "NY", 820, "Mid-Market", 8, "Y", "Y", "N", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Junction Textiles", "2027-01-15", "Kevin Wu", "CR-11434", 420000, "Amanda Foley", "Greensboro", "NC", 1320, "Enterprise", 7, "Y", "Y", "Y", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Keystone Robotics", "2027-02-28", "Tom Bradshaw", "CR-11467", 650000, "Ethan Vasquez", "Detroit", "MI", 2100, "Enterprise", 10, "Y", "Y", "N", "N", "Y", ""),
    ("Certify", "Sarah Chen", "Lincoln Metals", "2027-03-10", "Kevin Wu", "CR-11501", 310000, "Jordan Nakamura", "Birmingham", "AL", 880, "Mid-Market", 8, "Y", "Y", "Y", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Marlowe Agency", "2027-04-05", "Priya Patel", "CR-11534", 195000, "Nina Delgado", "Brooklyn", "NY", 520, "Mid-Market", 6, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Nightshade Chemicals", "2027-08-14", "Tom Bradshaw", "CR-11567", 580000, "Amanda Foley", "Baton Rouge", "LA", 1850, "Enterprise", 9, "Y", "Y", "N", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Oakmont Realty", "2027-09-22", "Kevin Wu", "CR-11601", 240000, "Jordan Nakamura", "Phoenix", "AZ", 640, "Mid-Market", 7, "Y", "Y", "Y", "Y", "Y", "Happy, full product set"),
    ("Chrome River", "Sarah Chen", "Patriot Freight", "2027-10-18", "Priya Patel", "CR-11634", 890000, "Ethan Vasquez", "Jacksonville", "FL", 2900, "Enterprise", 11, "Y", "Y", "Y", "Y", "N", "Big Payments opportunity"),
    ("Certify", "Sarah Chen", "Quillhaven Publishing", "2027-11-03", "Kevin Wu", "CR-11667", 155000, "Nina Delgado", "Boston", "MA", 340, "Mid-Market", 6, "Y", "Y", "Y", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Rosewater Beverages", "2028-01-24", "Tom Bradshaw", "CR-11701", 410000, "Amanda Foley", "Louisville", "KY", 1280, "Enterprise", 8, "Y", "Y", "Y", "N", "Y", ""),
    ("Certify", "Sarah Chen", "Sagebrush Ranch", "2028-02-11", "Kevin Wu", "CR-11734", 205000, "Jordan Nakamura", "Boise", "ID", 480, "Mid-Market", 7, "Y", "Y", "Y", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Terracotta Tile", "2028-03-22", "Priya Patel", "CR-11767", 315000, "Nina Delgado", "Albuquerque", "NM", 910, "Mid-Market", 9, "Y", "Y", "N", "Y", "Y", ""),
    ("Chrome River", "Sarah Chen", "Umbra Security", "2028-04-09", "Tom Bradshaw", "CR-11801", 540000, "Ethan Vasquez", "Arlington", "VA", 1680, "Enterprise", 10, "Y", "Y", "N", "Y", "N", ""),
    ("Chrome River", "Sarah Chen", "Viewcrest Media", "2028-08-30", "Priya Patel", "CR-11834", 470000, "Amanda Foley", "Los Angeles", "CA", 1450, "Enterprise", 8, "Y", "Y", "Y", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Waterline Maritime", "2028-09-14", "Kevin Wu", "CR-11867", 380000, "Jordan Nakamura", "Norfolk", "VA", 1100, "Enterprise", 7, "Y", "Y", "Y", "N", "Y", ""),
    ("Certify", "Sarah Chen", "Xander Systems", "2028-10-27", "Priya Patel", "CR-11901", 265000, "Nina Delgado", "Richmond", "VA", 710, "Mid-Market", 8, "Y", "Y", "Y", "Y", "Y", ""),
    ("Certify", "Sarah Chen", "Yellowpine Lumber", "2028-11-15", "Tom Bradshaw", "CR-11934", 190000, "Jordan Nakamura", "Eugene", "OR", 440, "Mid-Market", 6, "Y", "Y", "Y", "N", "Y", ""),
    ("Chrome River", "Sarah Chen", "Zenith Manufacturing", "2028-12-04", "Kevin Wu", "CR-11967", 760000, "Ethan Vasquez", "Milwaukee", "WI", 2400, "Enterprise", 9, "Y", "Y", "N", "Y", "N", ""),
    ("Chrome River", "Sarah Chen", "Beaufort Imports", "2026-08-25", "Priya Patel", "CR-12001", 360000, "Amanda Foley", "Savannah", "GA", 1080, "Enterprise", 7, "Y", "Y", "Y", "Y", "Y", "Clean account"),
    ("Certify", "Sarah Chen", "Delphi Gaming", "2028-05-22", "Kevin Wu", "CR-12034", 95000, "", "Austin", "TX", 180, "SMB", 10, "Y", "N", "N", "N", "N", "Small account but growing fast"),
    ("Certify", "Sarah Chen", "Emerald Trades", "2029-02-19", "Tom Bradshaw", "CR-12067", 280000, "Nina Delgado", "Seattle", "WA", 760, "Mid-Market", 7, "Y", "Y", "Y", "Y", "Y", ""),
]

df = pd.DataFrame(rows, columns=COLUMNS)

out_path = Path(__file__).parent / "test_territory.xlsx"
df.to_excel(out_path, index=False)
print(f"Wrote {len(df)} accounts to {out_path}")
