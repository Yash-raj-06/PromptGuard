# Dataset sources and labels

Label schema (used by both the CSV files and the model): `safe` = 0, `malicious` = 1.

## Files

| File | Rows | Role |
| --- | --- | --- |
| `prompts.csv` | 300 (150 safe / 150 malicious) | Authored training data |
| `external_train.csv` | 546 (343 safe / 203 malicious) | Real data used **only for training** |
| `external_test.csv` | 116 (56 safe / 60 malicious) | Independent holdout, **never trained on** |

## `prompts.csv` - hand-authored (synthetic)

All 300 rows were written by hand for this student project. They cover:

- ordinary benign requests;
- harmless uses of the words *ignore, instructions, system, prompt*;
- educational discussion about prompt injection and AI security;
- **quoted malicious instructions being analyzed, translated, classified, or summarized** (labelled `safe`);
- fiction / tabletop / security-research scenarios;
- malicious families: direct injection, instruction override / hidden-prompt
  extraction, role-play / jailbreak, indirect and paraphrased injections, and
  obfuscated formatting.

No text is labelled `malicious` only because it contains a keyword.

Because these are synthetic, they should not be treated as representative
production data.

## `external_train.csv` / `external_test.csv` - real data

- Source: `deepset/prompt-injections` on HuggingFace.
- License: Apache-2.0 / CC-BY-4.0 (dataset card).
- Downloaded by `backend/fetch_external_dataset.py` via the HuggingFace
  datasets-server rows API. The original columns are `text` (string) and
  `label` (int: 1 = injection, 0 = legitimate), remapped to `prompt` and
  `label` (`malicious` / `safe`).
- The **train** split is merged with the authored prompts for the
  `synthetic_plus_real` training strategy.
- The **test** split is held out. It is never used for training, feature
  fitting, or model selection. It is the independent evaluation.

## Leakage controls

- The authored dataset is split before the TF-IDF vectorizer is fit.
- The vectorizer is fit on the training split only.
- Model/algorithm selection uses cross-validation on training data only.
- `fetch_external_dataset.py` removes any external row that duplicates an
  authored prompt, and removes train rows that also appear in the test split
  (0 overlaps were found).
