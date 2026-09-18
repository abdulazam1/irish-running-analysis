import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from sqlalchemy import create_engine

engine = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results")
)

df = pd.read_sql("SELECT * FROM parkrun", engine)

df["race_date"] = pd.to_datetime(df["race_date"], format="%d/%m/%Y")

def time_to_seconds(t):
    try:
        parts = str(t).strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except:
        return None

df["finish_seconds"] = df["finish_time"].apply(time_to_seconds)
df = df.dropna(subset=["finish_seconds"])
df = df[(df["finish_seconds"] >= 600) & (df["finish_seconds"] <= 7200)]
df = df.sort_values("race_date")

sns.set_theme(style="darkgrid")
fig, axes = plt.subplots(3, 1, figsize=(14, 16))

fig.suptitle("Bushy Dublin Parkrun — Longitudinal Analysis", fontsize=16, fontweight="bold")
fig.subplots_adjust(top=0.93, hspace=0.4)

palette = sns.color_palette("muted")

# total finishers by race
finishers = df.groupby(["race_id", "race_date"]).size().reset_index(name="finishers")
finishers = finishers.sort_values("race_date")

ax1 = axes[0]
ax1.fill_between(finishers["race_date"], finishers["finishers"], alpha=0.3, color=palette[0])
ax1.plot(finishers["race_date"], finishers["finishers"], color=palette[0], linewidth=1.5)
finishers["rolling"] = finishers["finishers"].rolling(window=10, min_periods=1).mean()
ax1.plot(finishers["race_date"], finishers["rolling"], color="red", linewidth=2,
         linestyle="--", label="10-event rolling avg")
ax1.set_title("Total Finishers Per Race Over Time", fontsize=13, fontweight="bold", pad=8)
ax1.set_ylabel("Number of Finishers")
ax1.set_xlabel("")
ax1.legend()
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax1.xaxis.set_major_locator(mdates.YearLocator())

# gender split
gender = df.groupby(["race_date", "gender"]).size().reset_index(name="count")
gender_pivot = gender.pivot(index="race_date", columns="gender", values="count").fillna(0)
gender_pivot["total"] = gender_pivot.sum(axis=1)
if "Male" in gender_pivot.columns:
    gender_pivot["pct_male"]   = gender_pivot["Male"]   / gender_pivot["total"] * 100
if "Female" in gender_pivot.columns:
    gender_pivot["pct_female"] = gender_pivot["Female"] / gender_pivot["total"] * 100
gender_pivot["pct_male_roll"]   = gender_pivot["pct_male"].rolling(10, min_periods=1).mean()
gender_pivot["pct_female_roll"] = gender_pivot["pct_female"].rolling(10, min_periods=1).mean()

ax2 = axes[1]
ax2.plot(gender_pivot.index, gender_pivot["pct_male_roll"],
         color=palette[0], linewidth=2, label="Male %")
ax2.plot(gender_pivot.index, gender_pivot["pct_female_roll"],
         color=palette[3], linewidth=2, label="Female %")
ax2.fill_between(gender_pivot.index, gender_pivot["pct_male_roll"],
                 gender_pivot["pct_female_roll"], alpha=0.15, color="grey")
ax2.axhline(50, color="black", linestyle=":", linewidth=1, alpha=0.5)
ax2.set_title("Gender Split Over Time", fontsize=13, fontweight="bold", pad=8)
ax2.set_ylabel("Percentage of Finishers (%)")
ax2.set_xlabel("")
ax2.legend()    
ax2.set_ylim(0, 100)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax2.xaxis.set_major_locator(mdates.YearLocator())

# aerage finish per race
avg_time = df.groupby(["race_id", "race_date"])["finish_seconds"].mean().reset_index()
avg_time = avg_time.sort_values("race_date")
avg_time["rolling"] = avg_time["finish_seconds"].rolling(window=10, min_periods=1).mean()

def fmt_seconds(s, _):
    m, sec = divmod(int(s), 60)
    return f"{m}:{sec:02d}"

ax3 = axes[2]
ax3.scatter(avg_time["race_date"], avg_time["finish_seconds"],
            alpha=0.4, s=15, color=palette[2], label="Race avg")
ax3.plot(avg_time["race_date"], avg_time["rolling"],
         color="red", linewidth=2, linestyle="--", label="10-event rolling avg")
ax3.set_title("Average Finish Time Per Race Over Time", fontsize=13, fontweight="bold", pad=8)
ax3.set_ylabel("Average Finish Time (mm:ss)")
ax3.set_xlabel("Year")
ax3.legend()
ax3.yaxis.set_major_formatter(plt.FuncFormatter(fmt_seconds))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.xaxis.set_major_locator(mdates.YearLocator())

plt.savefig("data/parkrun_analysis.png", dpi=150, bbox_inches="tight")
print("Saved to data/parkrun_analysis.png")
plt.show()