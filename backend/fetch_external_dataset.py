"""Download INDEPENDENTLY-SOURCED prompt-injection data.

Source : deepset/prompt-injections  (HuggingFace)
License: Apache-2.0 / CC-BY-4.0 (dataset card)
API    : HuggingFace datasets-server rows endpoint (JSON, no extra deps)

Splits are saved with the project schema (prompt,label) where label is
'malicious' or 'safe':
    dataset/external_train.csv  (546 rows)  -> used only to train
    dataset/external_test.csv   (116 rows)  -> strictly held out, never trained on

Any prompt that also appears in dataset/prompts.csv is removed so the external
sets stay disjoint from the authored data.

Run from the backend folder:  python fetch_external_dataset.py
"""

import csv
import json
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BACKEND_DIR.parent
DATASET_DIR = PROJECT_DIR / "dataset"
TRAIN_PATH = DATASET_DIR / "prompts.csv"

API = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=deepset/prompt-injections&config=default&split={split}"
    "&offset={offset}&length={length}"
)
PAGE_SIZE = 100
LABEL_MAP = {0: "safe", 1: "malicious"}
SPLITS = {
    "train": DATASET_DIR / "external_train.csv",
    "test": DATASET_DIR / "external_test.csv",
}


def fetch_rows(split):
    rows = []
    offset = 0
    while True:
        url = API.format(split=split, offset=offset, length=PAGE_SIZE)
        with urllib.request.urlopen(url, timeout=60) as response:
            payload = json.load(response)
        page = payload.get("rows", [])
        if not page:
            break
        rows.extend(page)
        offset += PAGE_SIZE
        if offset >= payload.get("num_rows_total", 0):
            break
    return rows


def load_authored_prompts():
    if not TRAIN_PATH.exists():
        return set()
    import pandas as pd

    data = pd.read_csv(TRAIN_PATH)
    return set(data["prompt"].astype(str).str.strip())


def write_split(split, raw, exclude_prompts):
    seen = set()
    records = []
    dropped_overlap = 0
    for item in raw:
        row = item.get("row", item)
        text = str(row.get("text", "")).strip()
        label = LABEL_MAP.get(int(row.get("label")))
        if not text or label is None:
            continue
        if text in exclude_prompts:
            dropped_overlap += 1
            continue
        if text.lower() in seen:
            continue
        seen.add(text.lower())
        records.append({"prompt": text, "label": label})

    output_path = SPLITS[split]
    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["prompt", "label"])
        writer.writeheader()
        writer.writerows(records)

    safe = sum(1 for r in records if r["label"] == "safe")
    malicious = sum(1 for r in records if r["label"] == "malicious")
    print(f"[{split}] saved {len(records)} rows -> {output_path}")
    print(f"        safe={safe} malicious={malicious} (overlaps dropped: {dropped_overlap})")
    return records


def main():
    print("Fetching deepset/prompt-injections...")
    exclude = load_authored_prompts()
    for split in ("train", "test"):
        raw = fetch_rows(split)
        print(f"[{split}] downloaded {len(raw)} rows.")
        records = write_split(split, raw, exclude)
        # train split rows must not leak into the held-out test split
        exclude = exclude | {r["prompt"] for r in records}
    print("Source: deepset/prompt-injections (Apache-2.0/CC-BY-4.0).")


if __name__ == "__main__":
    main()
