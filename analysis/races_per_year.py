import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sqlalchemy import create_engine

engine = create_engine(os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/running_results"))

parkrun = pd.read_sql("SELECT race_id, race_date FROM parkrun", engine).drop_duplicates("race_id")
justrun = pd.read_sql("SELECT race_id, race_date FROM justrun", engine).drop_duplicates("race_id")

parkrun["year"] = pd.to_datetime(parkrun["race_date"], format="%d/%m/%Y", errors="coerce").dt.year
justrun["year"] = pd.to_datetime(justrun["race_date"], format="%d/%m/%Y", errors="coerce").dt.year

pr_by_year = parkrun.groupby("year")["race_id"].count().reset_index(name="races")
jr_by_year = justrun.groupby("year")["race_id"].count().reset_index(name="races")

all_years = sorted(set(pr_by_year["year"]).union(set(jr_by_year["year"])))
pr_by_year = pr_by_year.set_index("year").reindex(all_years, fill_value=0)
jr_by_year = jr_by_year.set_index("year").reindex(all_years, fill_value=0)


fig, ax = plt.subplots(figsize=(14, 7))
fig.patch.set_facecolor("#0f1117")
ax.set_facecolor("#1a1a2e")

title_color = "#ffffff"
label_color = "#cccccc"
grid_color  = "#2a2a3a"
c_parkrun   = "#4fc3f7"
c_justrun   = "#81c784"

x = np.arange(len(all_years))
w = 0.35

bars1 = ax.bar(x - w/2, pr_by_year["races"], w, color=c_parkrun, alpha=0.85, label="Parkrun")
bars2 = ax.bar(x + w/2, jr_by_year["races"], w, color=c_justrun, alpha=0.85, label="JustRun")

for bar in bars1:
    if bar.get_height() > 0:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                str(int(bar.get_height())), ha="center", va="bottom", color=label_color, fontsize=9)
for bar in bars2:
    if bar.get_height() > 0:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                str(int(bar.get_height())), ha="center", va="bottom", color=label_color, fontsize=9)

ax.set_xticks(x)
ax.set_xticklabels([str(int(y)) for y in all_years], color=label_color)
ax.set_ylabel("Number of Races", color=label_color)
ax.tick_params(colors=label_color)
ax.grid(color=grid_color, linestyle="--", linewidth=0.5, alpha=0.7, axis="y")
for spine in ax.spines.values():
    spine.set_edgecolor(grid_color)
ax.legend(fontsize=11, labelcolor=label_color, facecolor="#1a1a2e", edgecolor=grid_color)

fig.suptitle("Number of Races Per Year — Parkrun vs JustRun",
             color=title_color, fontsize=16, fontweight="bold")
fig.subplots_adjust(top=0.90)

import os
os.makedirs("data", exist_ok=True)
plt.savefig("data/races_per_year.png", dpi=150, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print("Saved to data/races_per_year.png")
plt.show()