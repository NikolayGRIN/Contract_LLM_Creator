import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

csv_path = Path("debug/retrieval_metrics_long_20260209_175054.csv")

df = pd.read_csv(csv_path)

pivot = df.pivot(index="method", columns="metric", values="value")

print("\n=== TABLE ===")
print(pivot.round(3))

# сохранить Excel
pivot.to_excel("debug/retrieval_metrics_table.xlsx")

metrics = ["recall@5", "recall@10", "precision@10", "mrr@10"]

for metric in metrics:
    plt.figure(figsize=(7,4))
    vals = pivot[metric]
    plt.bar(vals.index, vals.values)
    plt.xticks(rotation=25)
    plt.ylabel(metric)
    plt.title(f"Retrieval comparison — {metric}")
    plt.tight_layout()
    plt.savefig(f"debug/plot_{metric.replace('@','_')}.png")
    plt.close()

print("\nSaved:")
print("debug/retrieval_metrics_table.xlsx")
for m in metrics:
    print(f"debug/plot_{m.replace('@','_')}.png")
