import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from sqlalchemy import create_engine

engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results"))

# ── Load data ─────────────────────────────────────────────────────────────────

parkrun = pd.read_sql("SELECT * FROM parkrun", engine)
justrun = pd.read_sql("SELECT * FROM justrun", engine)
# Pre-filter: drop rows with null/empty/zero finish_time at load time
justrun = justrun[justrun["finish_time"].notna()]
justrun = justrun[justrun["finish_time"].str.strip().str.len() > 0]
justrun = justrun[justrun["finish_time"].str.strip() != "0:00:00"]

print(f"Parkrun rows: {len(parkrun)}, Justrun rows: {len(justrun)}")

# ── Clean times ───────────────────────────────────────────────────────────────

def time_to_seconds(t):
    if not t or pd.isna(t):
        return None
    t = str(t).strip()
    parts = t.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            hours = int(parts[0])
            mins  = int(parts[1])
            secs  = int(parts[2])
            # 0:MM:SS format (justrun stores times this way) — treat as MM:SS
            if hours == 0:
                return mins * 60 + secs
            else:
                return hours * 3600 + mins * 60 + secs
    except:
        return None

def seconds_to_mmss(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    m = int(s) // 60
    sec = int(s) % 60
    return f"{m}:{sec:02d}"

parkrun["finish_secs"] = parkrun["finish_time"].apply(time_to_seconds)
justrun["finish_secs"] = justrun["finish_time"].apply(time_to_seconds)

# Filter outliers
parkrun = parkrun[(parkrun["finish_secs"] >= 600) & (parkrun["finish_secs"] <= 7200)]

# ── Parse dates and filter to 2025+ ──────────────────────────────────────────

parkrun["date"] = pd.to_datetime(parkrun["race_date"], format="%d/%m/%Y", errors="coerce")
justrun["date"] = pd.to_datetime(justrun["race_date"], format="%d/%m/%Y", errors="coerce")

parkrun = parkrun.dropna(subset=["date"])
justrun = justrun.dropna(subset=["date"])

parkrun = parkrun[parkrun["date"].dt.year >= 2025]
justrun = justrun[justrun["date"].dt.year >= 2025]

print(f"Parkrun 2025+: {len(parkrun)} rows, {parkrun['race_id'].nunique()} races")
print(f"Justrun 2025+: {len(justrun)} rows, {justrun['race_id'].nunique()} races")
print(f"\nJustrun distances: {justrun['distance'].value_counts().to_string()}")

#all valid 5k road race times
valid_5k = [
    "5K", "Wine on the line 5k", "Glenstal 5K", "Laois GAA 5k", "Santa Dash 5k",
    "Rathangan Runners 5k", "Cill Dara Rugby Club  5k", "Alan Mahon 5k",
    "St Raphael's 5k", "Stoneyford 5k", "St Michaels Forest 5k",
    "Emo Forest Run 5k", "No Ordinary 5k", "Pudding Run  5k", "ABC 5K",
    "Rith Daingean Ui Chuis 5k", "Graig Rolling 5k", "Duckett Run 5k",
    "For the Boys 5k", "Rathvilly 5k", "Downs Ladies Football Club 5k",
    "MJ Bolton Memorial 5k", "Thomas Pender 5k", "Run in the Dark 5k",
    "Carlow Colts 5k", "Scoil Mhuire Clane 5k", "Maintain Hope 5k",
    "Newbridge FRC 5k", "Castleboro 5k", "Paddys Run 5k",
    "James Griffin Bro Leo 5k", "Ardagh Challenge 5k",
    "James Griffin Bro Leo 5k Unchipped",
]
justrun_5k = justrun[justrun["distance"].isin(valid_5k)]

justrun_5k = justrun_5k[(justrun_5k["finish_secs"] >= 780) & (justrun_5k["finish_secs"] <= 7200)]
justrun_5k = justrun_5k[justrun_5k["finish_time"].str.strip() != "0:00:00"]
print(f"\nJustrun 5K rows after time filter: {len(justrun_5k)}")

print("\nFastest 10 justrun 5K times:")
print(justrun_5k.nsmallest(10, "finish_secs")[["first_name","last_name","finish_time","finish_secs","distance","event_name"]].to_string())
print(f"Distances included:\n{justrun_5k['distance'].value_counts().to_string()}")

# gender standardisation

for df in [parkrun, justrun, justrun_5k]:
    df["gender"] = df["gender"].str.strip()
    df.loc[df["gender"].isin(["M", "m"]), "gender"] = "Male"
    df.loc[df["gender"].isin(["F", "f"]), "gender"] = "Female"

# Computes stats

def stats(df, label):
    return {
        "source":       label,
        "total_runners": len(df),
        "unique_runners": df["runner_id"].nunique(),
        "avg_time":      df["finish_secs"].mean(),
        "median_time":   df["finish_secs"].median(),
        "fastest_time":  df["finish_secs"].min(),
        "male_avg":      df[df["gender"]=="Male"]["finish_secs"].mean(),
        "female_avg":    df[df["gender"]=="Female"]["finish_secs"].mean(),
        "male_pct":      100 * (df["gender"]=="Male").sum() / len(df),
        "female_pct":    100 * (df["gender"]=="Female").sum() / len(df),
    }

parkrun_stats  = stats(parkrun,     "Parkrun (5km)")
justrun_stats  = stats(justrun_5k,  "JustRun (5km)")

for s in [parkrun_stats, justrun_stats]:
    print(f"\n{s['source']}: avg={seconds_to_mmss(s['avg_time'])} median={seconds_to_mmss(s['median_time'])} fastest={seconds_to_mmss(s['fastest_time'])}")



fig = plt.figure(figsize=(20, 24))
fig.patch.set_facecolor("#0f1117")

title_color = "#ffffff"
label_color = "#cccccc"
grid_color  = "#2a2a3a"
ax_bg       = "#1a1a2e"
c_parkrun   = "#4fc3f7"   
c_justrun   = "#81c784"   
c_male      = "#4fc3f7"
c_female    = "#f06292"

def style_ax(ax, title):
    ax.set_facecolor(ax_bg)
    ax.set_title(title, color=title_color, fontsize=13, fontweight="bold", pad=10)
    ax.tick_params(colors=label_color, labelsize=9)
    ax.xaxis.label.set_color(label_color)
    ax.yaxis.label.set_color(label_color)
    for spine in ax.spines.values():
        spine.set_edgecolor(grid_color)
    ax.grid(color=grid_color, linestyle="--", linewidth=0.5, alpha=0.7)

fig.suptitle("Parkrun vs JustRun — 5km Comparison (2025 onwards)",
             color=title_color, fontsize=18, fontweight="bold", y=0.97)

gs = fig.add_gridspec(4, 2, hspace=0.55, wspace=0.35,
                      left=0.08, right=0.95, top=0.92, bottom=0.04)

time_bins = list(range(600, 5400, 60))

ax1 = fig.add_subplot(gs[0, :])  
ax1.set_facecolor(ax_bg)
ax1.hist(parkrun["finish_secs"],  bins=time_bins, color=c_parkrun, alpha=0.5, label="Parkrun (5km)")
ax1.hist(justrun_5k["finish_secs"], bins=time_bins, color=c_justrun, alpha=0.5, label="JustRun (5km)")
ax1.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: seconds_to_mmss(x)))
ax1.xaxis.set_major_locator(ticker.MultipleLocator(300))
plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
ax1.set_xlabel("Finish Time", color=label_color)
ax1.set_ylabel("Number of Runners", color=label_color)
ax1.tick_params(colors=label_color)
for spine in ax1.spines.values():
    spine.set_edgecolor(grid_color)
ax1.grid(color=grid_color, linestyle="--", linewidth=0.5, alpha=0.7, axis="y")
ax1.legend(fontsize=10, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)

ax1.axvline(parkrun_stats["avg_time"],  color=c_parkrun, linestyle="--", linewidth=1.5,
            label=f"Parkrun avg {seconds_to_mmss(parkrun_stats['avg_time'])}")
ax1.axvline(justrun_stats["avg_time"],  color=c_justrun, linestyle="--", linewidth=1.5,
            label=f"JustRun avg {seconds_to_mmss(justrun_stats['avg_time'])}")
ax1.legend(fontsize=9, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)

# Average time comparison
ax2 = fig.add_subplot(gs[1, 0])
categories = ["Overall Avg", "Male Avg", "Female Avg"]
parkrun_times = [parkrun_stats["avg_time"], parkrun_stats["male_avg"], parkrun_stats["female_avg"]]
justrun_times = [justrun_stats["avg_time"], justrun_stats["male_avg"], justrun_stats["female_avg"]]

x = np.arange(len(categories))
w = 0.35
bars1 = ax2.bar(x - w/2, parkrun_times, w, color=c_parkrun, alpha=0.8, label="Parkrun")
bars2 = ax2.bar(x + w/2, justrun_times, w, color=c_justrun, alpha=0.8, label="JustRun")

ax2.set_xticks(x)
ax2.set_xticklabels(categories, color=label_color)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: seconds_to_mmss(x)))
ax2.set_ylabel("Avg Finish Time", color=label_color)
ax2.legend(fontsize=9, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)

# Label bars
for bar in bars1:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
             seconds_to_mmss(bar.get_height()), ha="center", va="bottom",
             color=label_color, fontsize=8)
for bar in bars2:
    ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20,
             seconds_to_mmss(bar.get_height()), ha="center", va="bottom",
             color=label_color, fontsize=8)
style_ax(ax2, "Average Finish Time Comparison (5km)")

# Gender split comparison
ax3 = fig.add_subplot(gs[1, 1])
sources = ["Parkrun", "JustRun 5km"]
male_pcts   = [parkrun_stats["male_pct"],   justrun_stats["male_pct"]]
female_pcts = [parkrun_stats["female_pct"], justrun_stats["female_pct"]]

x = np.arange(len(sources))
ax3.bar(x, male_pcts,   color=c_male,   alpha=0.8, label="Male %")
ax3.bar(x, female_pcts, bottom=male_pcts, color=c_female, alpha=0.8, label="Female %")
ax3.set_xticks(x)
ax3.set_xticklabels(sources, color=label_color)
ax3.set_ylabel("% of Runners", color=label_color)
ax3.set_ylim(0, 100)
ax3.axhline(50, color="white", linewidth=0.8, linestyle=":", alpha=0.5)
ax3.legend(fontsize=9, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
# Labels
for i, (m, f) in enumerate(zip(male_pcts, female_pcts)):
    ax3.text(i, m/2,       f"{m:.1f}%",   ha="center", color="white", fontsize=9, fontweight="bold")
    ax3.text(i, m + f/2,   f"{f:.1f}%",   ha="center", color="white", fontsize=9, fontweight="bold")
style_ax(ax3, "Gender Split Comparison (2025+)")

# Competitive zone breakout
ax4 = fig.add_subplot(gs[2, 0])
def zone_pcts(df):
    total = len(df)
    comp  = 100 * (df["finish_secs"] < 1500).sum() / total
    rec   = 100 * ((df["finish_secs"] >= 1500) & (df["finish_secs"] < 2400)).sum() / total
    fun   = 100 * (df["finish_secs"] >= 2400).sum() / total
    return comp, rec, fun

pr_comp, pr_rec, pr_fun = zone_pcts(parkrun)
jr_comp, jr_rec, jr_fun = zone_pcts(justrun_5k)

zones    = ["Competitive\n(<25 min)", "Recreational\n(25–40 min)", "Fun Runner\n(>40 min)"]
pr_vals  = [pr_comp, pr_rec, pr_fun]
jr_vals  = [jr_comp, jr_rec, jr_fun]
zone_colours = ["#81c784", "#4fc3f7", "#f06292"]

x = np.arange(len(zones))
bars1 = ax4.bar(x - w/2, pr_vals, w, color=zone_colours, alpha=0.8, label="Parkrun")
bars2 = ax4.bar(x + w/2, jr_vals, w, color=zone_colours, alpha=0.5, label="JustRun", edgecolor="white", linewidth=0.8)
ax4.set_xticks(x)
ax4.set_xticklabels(zones, color=label_color, fontsize=8)
ax4.set_ylabel("% of Runners", color=label_color)
ax4.legend(fontsize=9, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
for bar in list(bars1) + list(bars2):
    ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
             f"{bar.get_height():.1f}%", ha="center", va="bottom", color=label_color, fontsize=8)
style_ax(ax4, "Participation Type Breakdown (2025+)")

# Monthly participation over 2025
ax5 = fig.add_subplot(gs[2, 1])
parkrun["month"] = parkrun["date"].dt.to_period("M")
justrun["month"] = justrun["date"].dt.to_period("M")

pr_monthly = parkrun.groupby("month")["runner_id"].count().reset_index()
jr_monthly = justrun.groupby("month")["runner_id"].count().reset_index()

pr_monthly["month_dt"] = pr_monthly["month"].dt.to_timestamp()
jr_monthly["month_dt"] = jr_monthly["month"].dt.to_timestamp()

ax5.plot(pr_monthly["month_dt"], pr_monthly["runner_id"], color=c_parkrun, linewidth=2, marker="o", markersize=4, label="Parkrun")
ax5.plot(jr_monthly["month_dt"], jr_monthly["runner_id"], color=c_justrun, linewidth=2, marker="o", markersize=4, label="JustRun (all distances)")
ax5.set_ylabel("Total Runners", color=label_color)
import matplotlib.dates as mdates
ax5.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
ax5.xaxis.set_major_locator(mdates.MonthLocator())
plt.setp(ax5.xaxis.get_majorticklabels(), rotation=45, ha="right", fontsize=8)
ax5.legend(fontsize=9, labelcolor=label_color, facecolor=ax_bg, edgecolor=grid_color)
style_ax(ax5, "Monthly Participation (2025+)")

# Runner overlap
ax6 = fig.add_subplot(gs[3, :])
ax6.set_facecolor(ax_bg)
ax6.axis("off")

pr_ids = set(parkrun["runner_id"])
jr_ids = set(justrun["runner_id"])
overlap = pr_ids & jr_ids
only_pr = pr_ids - jr_ids
only_jr = jr_ids - pr_ids

rows = [
    ["", "Parkrun (2025+)", "JustRun (2025+)"],
    ["Total entries",        f"{len(parkrun):,}",             f"{len(justrun):,}"],
    ["Unique runners",       f"{len(pr_ids):,}",              f"{len(jr_ids):,}"],
    ["Races",                f"{parkrun['race_id'].nunique()}", f"{justrun['race_id'].nunique()}"],
    ["Avg finish time (5km)",f"{seconds_to_mmss(parkrun_stats['avg_time'])}",  f"{seconds_to_mmss(justrun_stats['avg_time'])}"],
    ["Male %",               f"{parkrun_stats['male_pct']:.1f}%",   f"{justrun_stats['male_pct']:.1f}%"],
    ["Female %",             f"{parkrun_stats['female_pct']:.1f}%", f"{justrun_stats['female_pct']:.1f}%"],
]

table = ax6.table(cellText=rows[1:], colLabels=rows[0],
                  loc="center", cellLoc="center")
table.auto_set_font_size(False)
table.set_fontsize(11)
table.scale(1, 2.2)

for (row, col), cell in table.get_celld().items():
    cell.set_facecolor("#1a1a2e" if row % 2 == 0 else "#12122a")
    cell.set_edgecolor(grid_color)
    cell.set_text_props(color=title_color if row == 0 else label_color)
    if row == 0:
        cell.set_facecolor("#2a2a4a")
        cell.set_text_props(color=title_color, fontweight="bold")

ax6.set_title("Summary Statistics", color=title_color, fontsize=13,
              fontweight="bold", pad=10)

import os
os.makedirs("data", exist_ok=True)
plt.savefig("data/comparison_analysis.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved to data/comparison_analysis.png")
plt.show()