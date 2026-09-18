import os
import json, time, requests
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import create_engine, text

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")

RACE_IDS = [
    260900, 269625, 269627, 269630, 277570, 277581, 277586, 279712, 280520,
    280863, 280864, 282908, 283217, 283221, 283877, 286911, 293053, 294862,
    295567, 295570, 296102, 301346, 307860, 312313, 312449, 315493, 317516,
    317525, 317893, 319180, 319514, 320193, 321829, 321902, 322068, 325531,
    326317, 329332, 330070, 330071, 330198, 331381, 331652, 331653, 332087,
    333379, 334419, 334569, 334850, 335031, 335918, 335921, 336617, 337802,
    337804, 338429, 340308, 340310, 341572, 342270, 343634, 343851, 343856,
    344905, 345566, 345640, 345648, 347473, 347474, 347475, 347477, 347479,
    348482, 348484, 351851, 352034, 353430, 354929, 355036, 356717, 356718,
    358578, 358880, 358911, 358925, 361097, 362913, 362916, 363840, 365660,
    367248, 367252, 367297, 367302, 368890, 372155, 373377, 375556, 376723,
    377044, 377324, 378562, 385144, 385166, 386544, 386548, 386569
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch_date(race_id):
    r = requests.get(f"https://my.raceresult.com/{race_id}/", headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", {"type": "application/ld+json"})
    if not script:
        return None
    data = json.loads(script.string)
    start = data.get("startDate")
    if not start:
        return None
    # Parse YYYY-MM-DD or DD/MM/YYYY
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(start.strip(), fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return None

engine = create_engine(DB_URL)
updated, failed = 0, []

with engine.begin() as conn:
    for race_id in RACE_IDS:
        date = fetch_date(race_id)
        if date:
            conn.execute(
                text("UPDATE justrun SET race_date = :date WHERE race_id = :rid"),
                {"date": date, "rid": race_id}
            )
            print(f"  {race_id}: {date} ✓")
            updated += 1
        else:
            print(f"  {race_id}: no date found ✗")
            failed.append(race_id)
        time.sleep(0.3)

print(f"\nDone — {updated} updated, {len(failed)} failed")
if failed:
    print(f"Failed: {failed}")
    # this code just fixes up the db for justrun.