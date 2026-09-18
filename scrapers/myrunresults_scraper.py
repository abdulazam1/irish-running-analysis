import os
import requests
import pandas as pd
import time
import hashlib
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.dialects.postgresql import insert

RUNNER_API = "https://api.myrunresults.com/api/PublicEvent/GetRunnersStatsAll?toggle=1"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json"
}


def reformat_date(date_str):
    if not date_str:
        return None
    clean = str(date_str).strip().split("+")[0].split("Z")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str.strip()


def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


# Get last 200 races. unsuccessful past 100.
def get_last_n_races(n=200):
    print(f"Fetching last {n} races...")
    driver = make_driver()
    races = []

    try:
        # loads the main page for cookies
        driver.get("https://www.myrunresults.com/race-results/all")
        time.sleep(6)

        # use JS fetch to call the API with a large maxResultCount
        script = """
        const response = await fetch(
            "https://api.myrunresults.com/api/PublicEvent/GetRaceResults?skipCount=0&maxResultCount=200&search=&showVirtual=true&showNormal=true",
            { headers: { "Accept": "application/json" } }
        );
        return await response.json();
        """
        data = driver.execute_async_script("""
            const callback = arguments[arguments.length - 1];
            fetch("https://api.myrunresults.com/api/PublicEvent/GetRaceResults?skipCount=0&maxResultCount=200&search=&showVirtual=true&showNormal=true",
                  { headers: { "Accept": "application/json" } })
                .then(r => r.json())
                .then(data => callback(data))
                .catch(e => callback(null));
        """)

        if not data:
            print("JS fetch failed, falling back to log intercept...")
            raise Exception("no data")

        for race in (data.get("items") or [])[:n]:
            races.append({
                "race_id":    race.get("raceId"),
                "event_name": race.get("raceName", ""),
                "race_date":  reformat_date(race.get("raceScheduledStartDate")),
                "race_slug":  race.get("raceSlug") or race.get("raceName", "").lower().replace(" ", "_"),
            })
        print(f"Found {len(races)} races via JS fetch")

    except Exception as e:
        print(f"JS fetch error: {e}, trying log intercept...")
        # fall intercepts what the page loaded naturally
        for entry in driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") != "Network.responseReceived":
                    continue
                url = msg["params"]["response"].get("url", "")
                if "GetRaceResults" not in url:
                    continue
                req_id = msg["params"]["requestId"]
                body   = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                data   = json.loads(body.get("body", "{}"))
                for race in (data.get("items") or [])[:n]:
                    races.append({
                        "race_id":    race.get("raceId"),
                        "event_name": race.get("raceName", ""),
                        "race_date":  reformat_date(race.get("raceScheduledStartDate")),
                        "race_slug":  race.get("raceSlug") or race.get("raceName", "").lower().replace(" ", "_"),
                    })
                print(f"Found {len(races)} races via log intercept")
                break
            except Exception:
                continue
    finally:
        driver.quit()

    return races


# get runners class and results through selenium
def get_runners_via_selenium(race_id, race_slug, event_name, race_date):
    """Load the race results page and intercept the GetRunnersStatsAll POST call directly."""

    results_url = f"https://www.myrunresults.com/events/{race_slug}/{race_id}/results"
    print(f"  Loading: {results_url}")

    driver = make_driver()
    all_results = []

    try:
        driver.get(results_url)
        time.sleep(8)

        for entry in driver.get_log("performance"):
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") != "Network.requestWillBeSent":
                    continue
                req  = msg["params"]["request"]
                url  = req.get("url", "")
                if "GetRunnersStats" not in url:
                    continue

                post_body = req.get("postData")
                if not post_body:
                    continue

                payload = json.loads(post_body)
                runner_class = payload.get("option", {}).get("runnerClass", "")
                print(f"  Detected runnerClass: '{runner_class}'")

                # paginates through all runners with correct runnerclass.
                skip = 0
                page_size = 50
                distance = runner_class

                while True:
                    payload["maxResultCount"] = page_size
                    payload["skipCount"]      = skip
                    payload["option"]["runnerClass"] = runner_class

                    response = requests.post(
                        RUNNER_API + f"&skipCount={skip}&maxResultCount={page_size}",
                        json=payload,
                        headers=HEADERS
                    )

                    if response.status_code != 200:
                        print(f"  API failed: {response.status_code}")
                        break

                    data  = response.json()
                    items = data.get("items", [])

                    if not items:
                        break

                    for runner in items:
                        first_name = runner.get("runner_FirstName")
                        last_name  = runner.get("runner_LastName")
                        gender     = runner.get("runner_Category")
                        club       = runner.get("runner_Club")
                        runner_id  = generate_runner_id(first_name, last_name, gender, club)

                        all_results.append({
                            "runner_id":  runner_id,
                            "race_id":    race_id,
                            "event_name": event_name,
                            "race_date":  race_date,
                            "distance":   distance,
                            "first_name": first_name,
                            "last_name":  last_name,
                            "gender":     gender,
                            "club":       club if club else "No Club",
                            "gross_time": runner.get("runner_GrossTime"),
                            "place":      runner.get("runner_Place"),
                        })

                    skip += page_size
                    time.sleep(0.5)

                print(f"  Fetched {len(all_results)} runners for runnerClass '{runner_class}'")
                break  # only intercept first matching call

            except Exception:
                continue

    finally:
        driver.quit()

    return all_results


# RUNNER ID
def generate_runner_id(first_name, last_name, gender, club):
    first_name = str(first_name).lower().strip()
    last_name  = str(last_name).lower().strip()
    gender     = str(gender).lower().strip()
    club       = str(club).lower().strip()
    if club in ("", "nan"):
        club = "no_club"
    return hashlib.md5(f"{first_name}|{last_name}|{gender}|{club}".encode()).hexdigest()


engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")
)
metadata = MetaData()
table = Table("myrunresults", metadata, autoload_with=engine)

races = get_last_n_races(200)

for race in races:
    print(f"\n{'='*50}")
    print(f"Scraping: {race['event_name']} (ID: {race['race_id']})")

    slug = race.get("race_slug") or race["event_name"].lower().replace(" ", "_").replace("&", "and")

    results = get_runners_via_selenium(
        race_id    = race["race_id"],
        race_slug  = slug,
        event_name = race["event_name"],
        race_date  = race["race_date"],
    )

    df = pd.DataFrame(results)
    print(f"Scraped {len(df)} runners")

    if not df.empty:
        with engine.begin() as conn:
            for row in df.to_dict(orient="records"):
                stmt = insert(table).values(**row)
                stmt = stmt.on_conflict_do_nothing(index_elements=["runner_id", "race_id"])
                conn.execute(stmt)
        print("Saved to PostgreSQL")

print("\nAll done!")