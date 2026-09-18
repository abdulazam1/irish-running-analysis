import os
import re
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, Table, MetaData
from sqlalchemy.dialects.postgresql import insert
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://www.parkrun.ie/bushydublin"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MScResearchBot/1.0)"}


def generate_runner_id(name, gender):
    name = str(name).lower().strip()
    gender = str(gender).lower().strip()
    return hashlib.md5(f"{name}|{gender}".encode()).hexdigest()


def reformat_date(date_str):
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str


def clean_time(raw):
    match = re.match(r"(\d{1,2}:\d{2}(?::\d{2})?)", raw.strip())
    return match.group(1) if match else raw.strip()


def make_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=options)


# Selenium to get event numbers and dates.
def get_all_events_with_dates():
    url = f"{BASE_URL}/results/eventhistory/"
    print("Starting browser to fetch all event history.")
    driver = make_driver()
    event_map = {}

    try:
        driver.get(url)
        time.sleep(5)
        for attempt in range(3):
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                break
            except:
                print(f"  Timeout attempt {attempt+1}, retrying.")
                driver.refresh()
                time.sleep(10)
        time.sleep(3)

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        if not rows:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 2:
                continue
            event_num = cells[0].text.strip()
            date_raw  = cells[1].text.strip()
            if event_num.isdigit() and date_raw:
                event_map[int(event_num)] = reformat_date(date_raw)

    finally:
        driver.quit()

    print(f"Found {len(event_map)} events")
    return event_map


# Parse the results table from BeautifulSoup

def parse_results(soup, event_number, race_date):
    event_name_tag = soup.find("h1")
    event_name = (
        event_name_tag.get_text(strip=True)
        if event_name_tag
        else f"Bushy Dublin parkrun #{event_number}"
    )

    table = soup.find("table")
    if not table:
        print(f"  No table found for event {event_number} — page may have different structure")
        print(f"  Page preview: {soup.get_text()[:300]}")
        return []

    rows = table.find_all("tr")
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    print(f"  Found table with {len(rows)} rows — Headers: {headers}")

    data = []
    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) == 0:
            continue

        if len(data) == 0:
            print(f"  First data row has {len(cols)} cols: {[c.get_text(strip=True)[:20] for c in cols]}")

        if len(cols) <= 5:
            continue

        try:
            name = (
                cols[1].find("a").text.strip()
                if cols[1].find("a")
                else cols[1].get_text(strip=True)
            )
            gender      = "Male" if "Male" in cols[2].get_text() else "Female"
            runner_id   = generate_runner_id(name, gender)
            time_raw    = cols[5].get_text(strip=True)

            if not time_raw:
                continue

            finish_time = clean_time(time_raw)
            place_raw   = cols[0].get_text(strip=True)

            if not place_raw.isdigit():
                continue

            data.append({
                "runner_id":   runner_id,
                "race_id":     event_number,
                "event_name":  event_name,
                "first_name":  name.split()[0],
                "last_name":   " ".join(name.split()[1:]),
                "gender":      gender,
                "club":        "No Club",
                "finish_time": finish_time,
                "place":       int(place_raw),
                "distance":    "5km",
                "race_date":   race_date,
            })

        except Exception as e:
            print(f"  Error on row: {e}")
            continue

    print(f"  Scraped {len(data)} runners")
    return data


# Scrape events and requests first, fixed and updated fallback to Selenium.

def scrape_event(event_number, race_date, selenium_driver=None):
    url = f"{BASE_URL}/results/{event_number}/"
    print(f"Scraping Event {event_number} ({race_date})")
    time.sleep(15)
    response = requests.get(url, headers=HEADERS)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        return parse_results(soup, event_number, race_date)

    # falls back to selenium in case of 405 error
    print(f"  requests got HTTP {response.status_code}, using Selenium...")
    selenium_driver.get(url)
    time.sleep(10)
    soup = BeautifulSoup(selenium_driver.page_source, "html.parser")
    return parse_results(soup, event_number, race_date)



event_map = get_all_events_with_dates()

selenium_driver = make_driver()

all_results = []
try:
    for event_number, race_date in event_map.items():
        if event_number >= 287:
            continue
        event_data = scrape_event(event_number, race_date, selenium_driver=selenium_driver)
        all_results.extend(event_data)
finally:
    selenium_driver.quit()

df = pd.DataFrame(all_results)
if not df.empty:
    print(df[["race_id", "race_date", "first_name", "finish_time"]].head(20))

# back up to CSV
df.to_csv("data/parkrun_below_287.csv", index=False)

# Save to SQL
engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")
)

metadata = MetaData()
parkrun = Table("parkrun", metadata, autoload_with=engine)

with engine.begin() as conn:
    for row in df.to_dict(orient="records"):
        stmt = insert(parkrun).values(**row)
        stmt = stmt.on_conflict_do_nothing(index_elements=["runner_id", "race_id"])
        conn.execute(stmt)

print("Saved to PostgreSQL (duplicates ignored)")
print("Done.")