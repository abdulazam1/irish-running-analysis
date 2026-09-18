import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
from sqlalchemy import create_engine
from datetime import datetime


engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")
)

df = pd.read_sql("SELECT * FROM parkrun", engine)
print(f"Loaded {len(df)} rows from parkrun table")


def time_to_seconds(t):
    if not t or pd.isna(t):
        return None
    t = str(t).strip()
    parts = t.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        return None
    return None

def seconds_to_mmss(s):
    if s is None or np.isnan(s):
        return ""
    m = int(s) // 60
    sec = int(s) % 60
    return f"{m}:{sec:02d}"

df["finish_secs"] = df["finish_time"].apply(time_to_seconds)
df = df[(df["finish_secs"] >= 600) & (df["finish_secs"] <= 7200)]

# Parse date
df["date"] = pd.to_datetime(df["race_date"], format="%d/%m/%Y", errors="coerce")
df = df.dropna(subset=["date"])
df = df.sort_values("date")

# Per-race aggregates
race_stats = df.groupby(["race_id", "date"]).agg(
    total_finishers  = ("runner_id", "count"),
    unique_runners   = ("runner_id", "nunique"),
    avg_time         = ("finish_secs", "mean"),
    fastest_time     = ("finish_secs", "min"),
).reset_index().sort_values("date")

# Fastest by gender per race
fastest_male = df[df["gender"] == "Male"].groupby(["race_id", "date"])["finish_secs"].min().reset_index()
fastest_male.columns = ["race_id", "date", "fastest_male"]
fastest_female = df[df["gender"] == "Female"].groupby(["race_id", "date"])["finish_secs"].min().reset_index()
fastest_female.columns = ["race_id", "date", "fastest_female"]

race_stats = race_stats.merge(fastest_male[["race_id","fastest_male"]], on="race_id", how="left")
race_stats = race_stats.merge(fastest_female[["race_id","fastest_female"]], on="race_id", how="left")

# Gender split
gender_counts = df.groupby(["race_id", "date", "gender"])["runner_id"].count().reset_index()
gender_counts.columns = ["race_id", "date", "gender", "count"]
gender_pivot = gender_counts.pivot_table(index=["race_id","date"], columns="gender", values="count", fill_value=0).reset_index()
gender_pivot["male_pct"]   = 100 * gender_pivot.get("Male", 0) / (gender_pivot.get("Male", 0) + gender_pivot.get("Female", 0))
gender_pivot["female_pct"] = 100 - gender_pivot["male_pct"]

# First-time vs returning runners
df_sorted = df.sort_values("date")
first_appearance = df_sorted.groupby("runner_id")["race_id"].first().reset_index()
first_appearance.columns = ["runner_id", "first_race_id"]
df2 = df.merge(first_appearance, on="runner_id")
df2["is_first_time"] = df2["race_id"] == df2["first_race_id"]
first_timer_stats = df2.groupby(["race_id","date"])["is_first_time"].mean().reset_index()
first_timer_stats.columns = ["race_id","date","first_timer_pct"]
first_timer_stats["first_timer_pct"] *= 100

time_bins = list(range(600, 7201, 60))  
def rolling(series, n=10):
    return series.rolling(n, min_periods=1).mean()

dates = race_stats["date"]



fig = plt.figure(figsize=(20, 28))
fig.patch.set_facecolor("#0f1117")

title_color   = "#ffffff"
label_color   = "#cccccc"
grid_color    = "#2a2a3a"
accent1       = "#4fc3f7"  
accent2       = "#f06292"  
accent3       = "#81c784"  
accent4       = "#ffb74d"  
accent5       = "#ce93d8"  
rolling_color = "#ff6b6b"  

ax_bg = "#1a1a2e"

def style_ax(ax, title):
    ax.set_facecolor(ax_bg)
    ax.set_title(title, color=title_color, fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(colors=label_color, labelsize=9)
    ax.xaxis.label.set_color(label_color)
    ax.yaxis.label.set_color(label_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(grid_color)
    ax.grid(color=grid_color, linestyle="--", linewidth=0.5, alpha=0.7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")

fig.suptitle("Bushy Dublin Parkrun — Full Longitudinal Analysis",
             color=title_color, fontsize=18, fontweight="bold", y=0.97)

gs = fig.add_gridspec(4, 2, hspace=0.55, wspace=0.35,
                      left=0.08, right=0.95, top=0.92, bottom=0.04)

# Total finishers per race
ax1 = fig.add_subplot(gs[0, 0])
ax1.fill_between(dates, race_stats["total_finishers"], alpha=0.3, color=accent1)
ax1.plot(dates, race_stats["total_finishers"], color=accent1, linewidth=0.8, alpha=0.6)
ax1.plot(dates, rolling(race_stats["total_finishers"]),
         color=rolling_color, linewidth=2, linestyle="--", label="10-event avg")
ax1.set_ylabel("Finishers", color=label_color)
ax1.legend(fontsize=8, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax1, "Total Finishers Per Race")

# Unique runners per race
ax2 = fig.add_subplot(gs[0, 1])
ax2.fill_between(dates, race_stats["unique_runners"], alpha=0.3, color=accent5)
ax2.plot(dates, race_stats["unique_runners"], color=accent5, linewidth=0.8, alpha=0.6)
ax2.plot(dates, rolling(race_stats["unique_runners"]),
         color=rolling_color, linewidth=2, linestyle="--", label="10-event avg")
ax2.set_ylabel("Unique Runners", color=label_color)
ax2.legend(fontsize=8, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax2, "Unique Runners Per Race")

# Fastest time per race
ax3 = fig.add_subplot(gs[1, 0])
ax3.scatter(dates, race_stats["fastest_time"], color=accent3, s=8, alpha=0.5, label="Overall fastest")
ax3.plot(dates, rolling(race_stats["fastest_time"]),
         color=accent3, linewidth=2, linestyle="--", label="Overall avg")
ax3.scatter(dates, race_stats["fastest_male"], color=accent1, s=8, alpha=0.5, label="Fastest male")
ax3.plot(dates, rolling(race_stats["fastest_male"]),
         color=accent1, linewidth=2, linestyle="--", label="Male avg")
ax3.scatter(dates, race_stats["fastest_female"], color=accent2, s=8, alpha=0.5, label="Fastest female")
ax3.plot(dates, rolling(race_stats["fastest_female"]),
         color=accent2, linewidth=2, linestyle="--", label="Female avg")
ax3.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: seconds_to_mmss(x)))
ax3.set_ylabel("Time (mm:ss)", color=label_color)
ax3.legend(fontsize=7, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color, ncol=2)
style_ax(ax3, "Fastest Time Per Race (Overall / Male / Female)")

# Average finish time per race
ax4 = fig.add_subplot(gs[1, 1])
ax4.scatter(dates, race_stats["avg_time"], color=accent4, s=8, alpha=0.5, label="Race avg")
ax4.plot(dates, rolling(race_stats["avg_time"]),
         color=rolling_color, linewidth=2, linestyle="--", label="10-event avg")
ax4.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: seconds_to_mmss(x)))
ax4.set_ylabel("Time (mm:ss)", color=label_color)
ax4.legend(fontsize=8, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax4, "Average Finish Time Per Race (5km only)")

# Gender split over time
ax5 = fig.add_subplot(gs[2, 0])
gp_dates = pd.to_datetime(gender_pivot["date"])
ax5.plot(gp_dates, rolling(gender_pivot["male_pct"]),   color=accent1, linewidth=2, label="Male %")
ax5.plot(gp_dates, rolling(gender_pivot["female_pct"]), color=accent2, linewidth=2, label="Female %")
ax5.fill_between(gp_dates, rolling(gender_pivot["male_pct"]),
                 rolling(gender_pivot["female_pct"]), alpha=0.1, color="white")
ax5.axhline(50, color="white", linewidth=0.8, linestyle=":", alpha=0.5)
ax5.set_ylabel("% of Finishers", color=label_color)
ax5.set_ylim(0, 100)
ax5.legend(fontsize=8, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax5, "Gender Split Over Time (10-event rolling avg)")

# First-time vs returning runners
ax7 = fig.add_subplot(gs[2, 1])
ft_dates = pd.to_datetime(first_timer_stats["date"])
ax7.fill_between(ft_dates, rolling(first_timer_stats["first_timer_pct"]), alpha=0.3, color=accent4)
ax7.plot(ft_dates, rolling(first_timer_stats["first_timer_pct"]),
         color=accent4, linewidth=2, label="First-timers %")
ax7.set_ylabel("% First-time Runners", color=label_color)
ax7.set_ylim(0, 100)
ax7.legend(fontsize=8, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax7, "First-Time vs Returning Runners")

# Finish time distribution
ax8 = fig.add_subplot(gs[3, 0])
ax8.set_facecolor(ax_bg)
counts, bins, patches = ax8.hist(
    df["finish_secs"], bins=time_bins, color=accent1, alpha=0.8, edgecolor=ax_bg
)

for patch, left in zip(patches, bins[:-1]):
    if left < 1500:       
        patch.set_facecolor(accent3)
    elif left < 2400:     
        patch.set_facecolor(accent1)
    else:                 
        patch.set_facecolor(accent2)

ax8.set_xlabel("Finish Time", color=label_color)
ax8.set_ylabel("Number of Runners", color=label_color)
ax8.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: seconds_to_mmss(x)))
ax8.xaxis.set_major_locator(ticker.MultipleLocator(300))
plt.setp(ax8.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
ax8.tick_params(colors=label_color, labelsize=9)
for spine in ax8.spines.values():
    spine.set_edgecolor(grid_color)
ax8.grid(color=grid_color, linestyle="--", linewidth=0.5, alpha=0.7, axis="y")
ax8.set_title("Finish Time Distribution (All Events)", color=title_color,
              fontsize=13, fontweight="bold", pad=10)

from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor=accent3, label="Competitive (<25 min)"),
    Patch(facecolor=accent1, label="Recreational (25–40 min)"),
    Patch(facecolor=accent2, label="Fun runner / Walker (>40 min)"),
]
ax8.legend(handles=legend_elements, fontsize=8, labelcolor=label_color,
           facecolor=ax_bg, edgecolor=grid_color)

plt.savefig("data/parkrun_full_analysis.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved to data/parkrun_full_analysis.png")
plt.show()