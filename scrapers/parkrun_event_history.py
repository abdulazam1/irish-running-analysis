from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import csv
import time

URL = "https://www.parkrun.ie/bushydublin/results/eventhistory/"

def reformat_date(date_str):
    """Try multiple input formats and return dd/mm/yyyy."""
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str  # return as-is if nothing matches

def scrape_event_history():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    print("Starting browser...")
    driver = webdriver.Chrome(options=options)

    events = []

    try:
        print(f"Fetching: {URL}")
        driver.get(URL)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "table")))
        time.sleep(3)

        rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
        if not rows:
            rows = driver.find_elements(By.CSS_SELECTOR, "table tr")

        print(f"Found {len(rows)} rows in table.")

        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if not cells:
                continue

            cell_texts = [c.text.strip() for c in cells]

            if len(cell_texts) >= 2:
                event_num = cell_texts[0]
                date = cell_texts[1]

                if event_num.isdigit() and any(c.isdigit() for c in date):
                    date = reformat_date(date)
                    events.append({"event": event_num, "date": date})

        # Fallback: links
        if not events:
            print("Table parse failed, trying link-based fallback...")
            import re
            links = driver.find_elements(By.CSS_SELECTOR, "a[href*='weeklyresults']")
            for link in links:
                text = link.text.strip()
                href = link.get_attribute("href")
                if text and href:
                    num_match = re.search(r"runSeqNumber=(\d+)", href)
                    event_num = num_match.group(1) if num_match else ""
                    events.append({"event": event_num, "date": reformat_date(text)})

    finally:
        driver.quit()

    return events


def main():
    events = scrape_event_history()

    if not events:
        print("\nNo events found. Try running without --headless to debug visually.")
        return

    print(f"\nFound {len(events)} events:\n")
    print(f"{'Event':<10} {'Date'}")
    print("-" * 30)
    for e in events:
        print(f"{e['event']:<10} {e['date']}")

    output_file = "bushy_dublin_parkrun_events.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["event", "date"])
        writer.writeheader()
        writer.writerows(events)

    print(f"\nSaved {len(events)} events to {output_file}")


if __name__ == "__main__":
    main()