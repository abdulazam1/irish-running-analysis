# Irish Running Event Data Analysis

An end-to-end Python data pipeline for collecting, cleaning, storing and analysing Irish running results from multiple public race-result sources. The project processed **50,000+ race records** and used PostgreSQL-backed analysis to explore participation trends, performance standards, demographic patterns and changes across events and years.

## What the project does

- Collects race and runner results from **Parkrun**, **MyRunResults** and **JustRun** using requests, BeautifulSoup, Selenium and API calls.
- Normalises inconsistent dates, finishing times and source-specific fields before persistence.
- Generates deterministic runner identifiers and uses database constraints/upserts to reduce duplicate records.
- Stores cleaned results in **PostgreSQL** for repeatable querying and analysis.
- Analyses participation and performance over time and compares results across data sources.
- Produces visualisations with **Pandas, Matplotlib and Seaborn**.

## Data flow

```text
Public race-result sources
        |
        v
Requests / BeautifulSoup / Selenium / APIs
        |
        v
Cleaning + normalisation + runner identification
        |
        v
PostgreSQL
        |
        v
Pandas analysis
        |
        v
Participation / performance / comparison visualisations
```

## Repository structure

```text
.
├── scrapers/
│   ├── parkrun_scraper.py
│   ├── myrunresults_scraper.py
│   ├── justrun_scraper.py
│   ├── parkrun_event_history.py
│   ├── myrunresults_event_history.py
│   └── justrun_date_backfill.py
├── analysis/
│   ├── parkrun_longitudinal_analysis.py
│   ├── parkrun_performance_analysis.py
│   ├── source_comparison_analysis.py
│   └── races_per_year.py
├── images/
├── data/sample/
├── .env.example
├── .gitignore
└── requirements.txt
```

## Example analysis

### Parkrun analysis

![Parkrun analysis](images/parkrun_analysis.png)

### Cross-source comparison

![Comparison analysis](images/comparison_analysis.png)

### Races per year

![Races per year](images/races_per_year.png)

## Technologies

**Python · PostgreSQL · SQLAlchemy · Pandas · NumPy · Matplotlib · Seaborn · Selenium · BeautifulSoup · Requests**

## Running locally

1. Clone the repository and create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a PostgreSQL database named `running_results` (or use another database name).
4. Set the `DATABASE_URL` environment variable. `.env.example` shows the expected format.
5. Run the relevant scraper(s), then run an analysis script.

Example on PowerShell:

```powershell
$env:DATABASE_URL="postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/running_results"
python scrapers/parkrun_scraper.py
python analysis/parkrun_longitudinal_analysis.py
```

## Data and privacy

Raw race-result exports are intentionally excluded from this repository. The project code is provided to demonstrate the collection, cleaning, database and analysis workflow without publishing the full scraped dataset or local database credentials.

## Background

This project was developed as a final-year Computer Science & Software Engineering project focused on building a multi-source running-results dataset and using it to investigate participation and performance patterns in Irish running events.
