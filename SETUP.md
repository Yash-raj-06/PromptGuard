# PromptGuard - Setup and Run Guide (Windows PowerShell)

Explainable Prompt Injection Detection System.

- Backend: Python 3.12 + FastAPI
- ML: scikit-learn (TF-IDF word + char n-grams + Logistic Regression), selected with pipeline cross-validation
- Explainable AI: LIME (explains the classifier; it is not the classifier)
- Attack types: transparent rule-based heuristic (not a learned multi-class model)
- Robustness: controlled transformations + consistency score
- Defensive policy: Allow / Flag for Review / Block (configurable thresholds)
- Frontend: React 19 + Vite 8 (3D glass UI, lucide-react icons)

---

## 1. Requirements

- Python 3.12.x (tested with 3.12.10)
- Node.js 22.x (tested with 22.20.0) and npm 10.x
- Windows PowerShell

Check versions:

```powershell
python --version
node --version
npm --version
```

---

## 2. First-time installation

### Backend

Run these from the `backend` folder:

```powershell
cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Frontend

Run these from the `frontend` folder. Always use `npm ci` (not a copied
`node_modules` folder from another computer) so the Windows native binaries
(`rolldown`, `lightningcss`) match your machine:

```powershell
cd frontend
npm ci
```

If `npm ci` fails, delete `node_modules` and retry:

```powershell
Remove-Item -Recurse -Force node_modules
npm ci
```

---

## 3. (Re)train the model

Only needed if you change the datasets. Run from `backend`:

```powershell
cd backend
python train_model.py
```

This writes `model.pkl`, `vectorizer.pkl`, and `model_info.json`.

The repository already contains `dataset/external_train.csv` and
`dataset/external_test.csv`. To re-download them from HuggingFace (needs
internet), run from `backend`:

```powershell
python fetch_external_dataset.py
```

See `dataset/SOURCES.md` for dataset provenance and the label schema.

---

## 4. Run the project

Open **two** PowerShell terminals.

### Terminal 1 - backend

```powershell
cd backend
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Backend runs at http://127.0.0.1:8000
Interactive docs: http://127.0.0.1:8000/docs

### Terminal 2 - frontend

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

The frontend calls the backend at `http://127.0.0.1:8000` by default. To point
it elsewhere, copy `frontend/.env.example` to `frontend/.env` and change
`VITE_API_BASE_URL`, then restart `npm run dev`.

The backend accepts CORS requests from any `localhost` / `127.0.0.1` port, so
the app still works if Vite falls back to a different port (for example when
5173 is already in use).

---

## 5. Run the tests

### Backend (pytest)

From `backend`:

```powershell
cd backend
python -m pytest -v
```

This runs all backend tests: `test_api.py` (core API/ML) and `test_features.py`
(attack types, robustness, policy, new endpoints).

### Frontend (lint + tests + build)

From `frontend`:

```powershell
cd frontend
npm run lint
npm test
npm run build
```

---

## 6. Stopping the servers

In each terminal press `Ctrl + C`.

To force-kill a stuck server on port 8000:

```powershell
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

---

## 7. Common problems

| Problem | Fix |
| --- | --- |
| `ModuleNotFoundError: No module named 'lime'` | `python -m pip install -r requirements.txt` from `backend`. |
| `ModuleNotFoundError: pandas._libs.pandas_parser` | Broken pandas install: `python -m pip install --force-reinstall --no-cache-dir pandas==2.3.3`. |
| Model metrics show "offline" | Start the backend (Terminal 1) and refresh. |
| `503` on `/predict`, `/analyze` or `/robustness` | Model artifacts missing. Run `python train_model.py`. |
| Frontend cannot reach backend / CORS error | Keep the backend on port 8000 and open the site at http://localhost:5173 (not a `file://` path). |
| `npm` native binding error (`rolldown` / `lightningcss`) | `Remove-Item -Recurse -Force node_modules` then `npm ci`. |
| Port already in use | Stop the other process or change `--port`. |

---

## 8. Attack type, robustness and recommendation

These features are separate from the binary Safe/Malicious prediction.

### Attack type (`backend/attack_types.py`)
A transparent **rule-based heuristic** with five categories plus
`Unknown / Uncertain`: instruction override, jailbreak/role-play,
system-prompt extraction, indirect injection, and obfuscation. Only prompts
classified `Malicious` are categorised; `Safe` prompts return
`Unknown / Uncertain` with `applicable: false`, so harmless discussion or
quotation of an attack is not mislabelled. The response includes
`method: "rule_based_heuristic"` and `is_learned: false`. There is no
multi-class labelled dataset in this project, so this is intentionally **not**
a trained multi-class classifier.

### Robustness (`backend/robustness.py`, `POST /robustness`)
Applies nine documented local transformations (uppercase, extra whitespace,
punctuation spacing/removal, leetspeak substitution, spaced letters, hyphenated
letters, last-two-letter typo, limited synonym paraphrase) and compares each
prediction with the original. The summary reports:

```
consistency_score = 100 * unchanged_predictions / evaluated transformations
```

Transformation or prediction failures are reported per row and never break the
request. A high score does **not** prove resistance to real attacks.

### Defensive recommendation (`backend/policy.py`, in `POST /analyze`)
Maps the actual malicious probability to:
- `Block` if `>= 0.85`
- `Flag for Review` if `>= 0.40` (includes the borderline 0.40-0.60 range)
- `Allow` otherwise

Thresholds are configurable before starting the backend:

```powershell
$env:PROMPTGUARD_BLOCK_THRESHOLD = "0.90"
$env:PROMPTGUARD_REVIEW_THRESHOLD = "0.50"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Recommendations are decision support only; a high probability is not proof of
malicious intent, and no enforcement integration is attached.

### New API endpoints
- `POST /analyze` - prediction + LIME + attack type + recommendation
- `POST /robustness` - `{"prompt": "...", "include_paraphrase": true}`

`/predict`, `/health` and `/model-info` keep their existing contracts.

---

## 9. Model evaluation results

Model selection uses **5-fold stratified cross-validation with the whole
pipeline** (TF-IDF is fit inside every fold), scoring macro-F1 on training data
only. The saved production model is the best pipeline refit on the full
training set. The external test split is used only once, for final reporting.

Actual results from the current artifacts (`backend/model_info.json`):

| Evaluation set | Accuracy | Macro-F1 | Malicious precision | Malicious recall |
| --- | --- | --- | --- | --- |
| Training CV (macro-F1) | - | 0.9367 | - | - |
| Authored held-out (75) | 0.8533 | 0.8524 | 0.7955 | 0.9459 |
| Independent external (116) | 0.8879 | 0.8873 | 1.0000 | 0.7833 |

External confusion matrix: `[[56, 0], [13, 47]]` -> 0 false positives,
**13 false negatives** (malicious prompts predicted Safe).

Known weaknesses (honest):

- 13 of 60 external malicious prompts are still missed. TF-IDF cannot
  generalize to unseen wording, other languages, or long conversational text.
- Some external `malicious` labels are noisy (for example short foreign-language
  phrases such as "translate to polish"), so a few "misses" are label issues,
  not model failures.
- This is a college project model, **not** production-grade detection.

---

## 10. Notes and limitations

- Training data mixes small **hand-authored synthetic** prompts
  (`dataset/prompts.csv`) with the real `deepset/prompt-injections` train split.
- The headline metrics come from the **independent external test split**
  (`dataset/external_test.csv`), which the model never trained on. They reflect
  realistic generalization and are **not** production-grade.
- The model uses TF-IDF bag-of-words features; it does not understand meaning.
- Attack categories are a **rule-based heuristic**, not a trained multi-class
  model, and are evidence estimates only.
- Robustness results cover a small deterministic set of transformations and do
  not prove resistance to arbitrary attacks.
- `Allow / Flag for Review / Block` are decision-support recommendations, not
  enforcement guarantees.
- LIME explanations show which words influenced a prediction. They are **not**
  proof of intent or causation, and LIME is not the classifier.
