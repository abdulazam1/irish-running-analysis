from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import time
import json
import csv

PAGE_URL = "https://www.myrunresults.com/race-results/all"


def reformat_date(date_str):
    clean = date_str.strip().split("+")[0].split("Z")[0]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d",
                "%m/%d/%y", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str.strip()


def scrape_latest_10():
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

    print("Starting browser...")
    driver = webdriver.Chrome(options=options)
    results = []

    try:
        driver.get(PAGE_URL)
        print("Waiting for API calls to fire...")
        time.sleep(8)

        logs = driver.get_log("performance")

        # Find the GetRaceResults call specifically
        for entry in logs:
            try:
                msg = json.loads(entry["message"])["message"]
                if msg.get("method") != "Network.responseReceived":
                    continue

                url = msg["params"]["response"].get("url", "")
                if "GetRaceResults" not in url:
                    continue

                print(f"Found: {url}")
                req_id = msg["params"]["requestId"]
                body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": req_id})
                data = json.loads(body.get("body", "{}"))

                print(f"Top-level keys: {list(data.keys())}")

                items = None
                for key, val in data.items():
                    if isinstance(val, list) and len(val) > 0:
                        items = val
                        print(f"Using key '{key}' → {len(items)} records")
                        print(f"Sample keys:   {list(items[0].keys())}")
                        break

                if not items:
                    print("No list found in response:", data)
                    break

                for item in items[:10]:
                    date = str(item.get("raceScheduledStartDate") or "")
                    event_name = str(item.get("raceName") or "")
                    distance = str(item.get("raceDistance") or "")
                    county   = str(item.get("raceCounty") or "")
                    race_type = str(item.get("raceType") or "")

                    results.append({
                        "date":       reformat_date(date),
                        "event_name": event_name,
                        "distance":   distance,
                        "county":     county,
                        "type":       race_type,
                    })
                break  

            except Exception:
                continue

    finally:
        driver.quit()

    return results


def main():
    results = scrape_latest_10()

    if not results:
        print("No results found.")
        return

    print(f"\n{'Date':<15} {'Event':<45} {'Distance':<12} {'County'}")
    print("-" * 85)
    for r in results:
        print(f"{r['date']:<15} {r['event_name']:<45} {r['distance']:<12} {r['county']}")

    with open("myrunresults_latest10.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "event_name", "distance", "county", "type"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved to myrunresults_latest10.csv")


if __name__ == "__main__":
    main()

    #no impact on system, used for early testing.