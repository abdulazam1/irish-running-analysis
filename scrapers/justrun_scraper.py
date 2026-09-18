import os
import re, json, time, hashlib, urllib.parse, requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine, Table, Column, Text, Integer, MetaData, UniqueConstraint
from sqlalchemy.dialects.postgresql import insert
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


JUSTRUN_URL = "https://justrunsevents.ie/event-results"
DB_URL      = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")
OUTPUT_CSV  = "data/justrun_results.csv"


def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    return webdriver.Chrome(options=options)

def reformat_date(date_str):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d %b %Y",
                "%B %d, %Y", "%d.%m.%Y", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str.strip()

def generate_runner_id(first, last, gender, club):
    key = f"{first}|{last}|{gender}|{club}".lower().strip()
    return hashlib.md5(key.encode()).hexdigest()

# Get race IDs from justrunsevents.ie

def get_all_events(driver):
    print("Fetching events from justrunsevents.ie...")
    events = []
    seen   = set()
    empty  = 0

    for year in range(datetime.now().year, 2018, -1):
        url = f"{JUSTRUN_URL}?year={year}"
        driver.get(url)
        time.sleep(3)

        soup  = BeautifulSoup(driver.page_source, "html.parser")
        links = [a for a in soup.find_all("a", href=True) if "raceresult.com" in a["href"]]

        if not links:
            empty += 1
            print(f"  {year}: no events (streak {empty})")
            if empty >= 2:
                break
            continue

        empty = 0
        for a in links:
            m = re.search(r"raceresult\.com/(\d+)", a["href"])
            if not m or m.group(1) in seen:
                continue
            race_id = m.group(1)
            seen.add(race_id)

            # Get event name and data
            event_name, event_date, location = "", "", ""
            card = (a.find_parent(class_=re.compile(r"event|card|row|item|result", re.I))
                    or a.find_parent("li") or a.find_parent("tr") or a.find_parent("div"))
            if card:
                for tag in card.find_all(["h2","h3","h4","strong","span","p","a"]):
                    txt = tag.get_text(strip=True)
                    if txt and txt.lower() not in ("results","") and not re.match(r"^\d", txt) and len(txt) > 3:
                        event_name = txt; break
                ds = card.find(string=re.compile(r"\d{1,2}[/ .-]\d{1,2}[/ .-]\d{2,4}"))
                if ds:
                    event_date = reformat_date(str(ds).strip())
                else:
                    d = card.find(class_=re.compile(r"\bday\b|date.?num", re.I))
                    m2 = card.find(class_=re.compile(r"\bmonth\b|date.?mon", re.I))
                    if d and m2:
                        event_date = reformat_date(f"{d.get_text(strip=True)} {m2.get_text(strip=True)} {year}")
                loc = card.find(class_=re.compile(r"locat|venue|address|pin", re.I))
                if loc:
                    location = loc.get_text(strip=True)

            events.append({"race_id": race_id, "year": year,
                           "event_name": event_name, "event_date": event_date, "location": location})

        print(f"  {year}: {len(links)} links → {len(events)} total")

    print(f"Found {len(events)} events total")
    return events

# load race page and grab the config

def get_race_config(driver, race_id):
    driver.get("about:blank")
    time.sleep(0.3)
    driver.execute_cdp_cmd("Network.enable", {})
    driver.get(f"https://my.raceresult.com/{race_id}/results")
    time.sleep(5)

    for log in driver.get_log("performance"):
        try:
            msg = json.loads(log["message"])["message"]
            if msg["method"] != "Network.responseReceived":
                continue
            url    = msg["params"]["response"]["url"]
            req_id = msg["params"]["requestId"]
            if "RRPublish/data/config" in url:
                body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                return json.loads(body["body"])
        except:
            continue
    return None

# Fetch runners with API pattern

def fetch_results(driver, race_id, config):
    """
    API response structure (confirmed):
      {
        "data": {
          "#1_Bikejoring":       [["BIB","ID","Rank","FullName","Gender","ChipTime"], ...],
          "#2_2 Dog Canicross":  [...],
          ...
        },
        "DataFields": ["BIB","ID","WithStatus([OverallRankp])","FLNAME","GenderMF","ChipTime"]
      }
    Each row is a list: [bib, id, place, full_name, gender, chip_time]
    """
    key      = config["key"]
    server   = config["server"]
    lists    = config["lists"]
    base_url = f"https://{server}/{race_id}/RRPublish/data/list"

    cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer":    f"https://my.raceresult.com/{race_id}/",
        "Accept":     "application/json, */*",
        "Origin":     "https://my.raceresult.com",
    }

    all_rows = []

    for lst in lists:
        encoded = urllib.parse.quote(lst["Name"], safe="")
        url     = (f"{base_url}?key={key}&listname={encoded}"
                   f"&page=results&contest=0&r=all&l=100000&openedGroups=%7B%7D&term=")

        try:
            r = requests.get(url, headers=headers, cookies=cookies, timeout=20)
        except Exception as e:
            print(f"    Request error: {e}")
            continue

        if r.status_code != 200:
            print(f"    [{r.status_code}] {lst['Name']}")
            continue

        resp        = r.json()
        data        = resp.get("data", {})
        data_fields = resp.get("DataFields", [])

        if not isinstance(data, dict) or not data:
            print(f"    [{r.status_code}] {lst['Name']} — empty data")
            continue

        print(f"    [{r.status_code}] {lst['Name']} — {sum(len(v) for v in data.values() if isinstance(v,list))} runners across {len(data)} contests")

        def col(name_fragments):
            for i, f in enumerate(data_fields):
                if any(frag.lower() in f.lower() for frag in name_fragments):
                    return i
            return None

        idx_place  = col(["rank", "place", "pos"])
        idx_name   = col(["flname", "name"])
        idx_gender = col(["gender", "sex"])
        idx_time   = col(["chiptime", "chip", "time"])
        idx_bib    = col(["bib"])
        print(f"    Columns → place={idx_place} name={idx_name} gender={idx_gender} time={idx_time} bib={idx_bib}")

        for contest_key, rows in data.items():
            if not isinstance(rows, list):
                continue
            # contest_key looks like "#4_5K Canicross"
            m = re.match(r"#(\d+)_(.*)", contest_key)
            contest_name = m.group(2) if m else contest_key

            for row in rows:
                if not isinstance(row, list) or len(row) < 3:
                    continue

                def get(idx):
                    return str(row[idx]).strip() if idx is not None and idx < len(row) else ""

                full_name  = get(idx_name)
                parts      = full_name.split()
                first_name = parts[0] if parts else ""
                last_name  = " ".join(parts[1:]) if len(parts) > 1 else ""
                gender_raw = get(idx_gender).upper()
                gender     = "Male" if gender_raw in ("M","MALE") else "Female" if gender_raw in ("F","FEMALE") else gender_raw
                place_raw  = re.sub(r"[^\d]", "", get(idx_place))
                place      = int(place_raw) if place_raw.isdigit() else None
                chip_time  = get(idx_time)
                bib        = get(idx_bib)

                all_rows.append({
                    "bib":        bib,
                    "contest":    contest_name,
                    "place":      place,
                    "first_name": first_name,
                    "last_name":  last_name,
                    "gender":     gender,
                    "chip_time":  chip_time,
                })

        break 

    return all_rows

# PostgreSQL Database

def init_db(engine):
    meta  = MetaData()
    table = Table("justrun", meta,
        Column("runner_id",   Text),
        Column("race_id",     Integer),
        Column("event_name",  Text),
        Column("race_date",   Text),
        Column("distance",    Text),
        Column("first_name",  Text),
        Column("last_name",   Text),
        Column("gender",      Text),
        Column("club",        Text),
        Column("finish_time", Text),
        Column("place",       Integer),
        UniqueConstraint("runner_id", "race_id", "distance",
                         name="uq_justrun_runner_race_distance"),
    )
    meta.create_all(engine)
    return table


def main():
    driver      = make_driver()
    engine      = create_engine(DB_URL)
    table       = init_db(engine)
    all_results = []
    failed      = []

    try:
        events = get_all_events(driver)

        for idx, event in enumerate(events, 1):
            race_id = event["race_id"]
            print(f"\n[{idx}/{len(events)}] Race {race_id}")

            config = get_race_config(driver, race_id)
            if not config:
                print("  No config — skipping")
                failed.append(race_id)
                continue

            event_name = event.get("event_name") or config.get("eventname", f"Race {race_id}")
            raw_date   = event.get("event_date") or config.get("date", config.get("eventdate", ""))
            race_date  = reformat_date(str(raw_date)) if raw_date else ""
            print(f"  {event_name} | {race_date}")

            rows = fetch_results(driver, race_id, config)
            print(f"  → {len(rows)} runners")

            parsed   = []
            inserted = 0
            for row in rows:
                runner_id = generate_runner_id(
                    row["first_name"], row["last_name"], row["gender"], ""
                )
                record = {
                    "runner_id":   runner_id,
                    "race_id":     int(race_id),
                    "event_name":  event_name,
                    "race_date":   race_date,
                    "distance":    row["contest"],
                    "first_name":  row["first_name"],
                    "last_name":   row["last_name"],
                    "gender":      row["gender"],
                    "club":        "",
                    "finish_time": row["chip_time"],
                    "place":       row["place"],
                }
                parsed.append(record)

            with engine.begin() as conn:
                for rec in parsed:
                    try:
                        conn.execute(table.insert().values(**rec))
                        inserted += 1
                    except Exception:
                        pass  

            print(f"  → {inserted} rows inserted into DB")
            all_results.extend(parsed)
            time.sleep(2)

    finally:
        driver.quit()

    df = pd.DataFrame(all_results)
    if not df.empty:
        print(f"\n{'='*60}")
        print(f"Total runners : {len(df)}")
        print(f"Unique races  : {df['race_id'].nunique()}")
        print(df[["race_id","event_name","distance","first_name","last_name","gender","finish_time"]].head(20).to_string())
        import os; os.makedirs("data", exist_ok=True)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"Saved → {OUTPUT_CSV}")
    else:
        print("No results scraped.")

    if failed:
        print(f"Failed races: {failed}")

if __name__ == "__main__":
    main()