from pathlib import Path
import json
import logging

import joblib
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from lime.lime_text import LimeTextExplainer

# ==============================
# PROMPTGUARD API
# ==============================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

MAX_PROMPT_LENGTH = 5000

app = FastAPI(
    title="PromptGuard API",
    description="Prompt Injection Detection with Explainable AI",
    version="1.0.0",
)

# ==============================
# CORS (local development)
# ==============================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================
# LOAD MODEL ARTIFACTS
# ==============================

model = None
vectorizer = None
classes = []
SAFE_INDEX = 0
MALICIOUS_INDEX = 1
MODEL_LOAD_ERROR = None

try:
    model = joblib.load(BASE_DIR / "model.pkl")
    vectorizer = joblib.load(BASE_DIR / "vectorizer.pkl")

    # This backend expects class 0 = Safe and class 1 = Malicious.
    classes = [int(c) for c in model.classes_]

    if 0 not in classes or 1 not in classes:
        raise ValueError(
            "Model must use numeric labels 0 (Safe) and 1 (Malicious)."
        )

    SAFE_INDEX = classes.index(0)
    MALICIOUS_INDEX = classes.index(1)

    logger.info("Model loaded. Classes: %s", classes)

except Exception as exc:  # noqa: BLE001 - report any loading failure safely
    MODEL_LOAD_ERROR = (
        "Model artifacts could not be loaded. Run backend/train_model.py first."
    )
    model = None
    vectorizer = None
    logger.exception("Failed to load model artifacts")

# ==============================
# MODEL INFORMATION
# ==============================

FALLBACK_MODEL_INFO = {
    "model": "Logistic Regression",
    "vectorizer": "TF-IDF",
    "ngram_range": [1, 2],
    "total_samples": 0,
    "training_samples": 0,
    "testing_samples": 0,
    "safe_samples": 0,
    "malicious_samples": 0,
    "feature_count": 0,
    "test_size": 0.25,
    "random_state": 42,
    "accuracy": None,
    "precision": None,
    "recall": None,
    "f1_score": None,
    "macro_f1": None,
    "weighted_f1": None,
    "confusion_matrix": {"labels": ["Safe", "Malicious"], "values": [[0, 0], [0, 0]]},
}

try:
    with open(BASE_DIR / "model_info.json", "r", encoding="utf-8") as file:
        model_info = json.load(file)
except (FileNotFoundError, json.JSONDecodeError):
    logger.warning("model_info.json missing or invalid; using fallback.")
    model_info = dict(FALLBACK_MODEL_INFO)

# ==============================
# LIME EXPLAINER
# ==============================

explainer = LimeTextExplainer(class_names=["Safe", "Malicious"], random_state=42)

# ==============================
# REQUEST MODEL
# ==============================

class PromptRequest(BaseModel):
    prompt: str


# ==============================
# VALIDATION ERROR HANDLER
# ==============================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Return a clean, non-leaky message instead of the raw validation dump.
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request. Send JSON with a non-empty string field 'prompt'."
        },
    )


# ==============================
# LIME PREDICTION FUNCTION
# ==============================

def predict_proba(texts):
    vectors = vectorizer.transform(texts)
    probabilities = model.predict_proba(vectors)
    # LIME expects columns ordered as [Safe, Malicious].
    return probabilities[:, [SAFE_INDEX, MALICIOUS_INDEX]]


# ==============================
# HOME
# ==============================

@app.get("/")
def home():
    return {
        "message": "PromptGuard API is running",
        "status": "online",
        "version": "1.0.0",
    }


# ==============================
# HEALTH CHECK
# ==============================

@app.get("/health")
def health():
    return {"status": "online", "model_loaded": model is not None}


# ==============================
# MODEL INFORMATION
# ==============================

@app.get("/model-info")
def get_model_info():
    info = dict(model_info)
    info["model_loaded"] = model is not None
    return info


# ==============================
# PROMPT PREDICTION
# ==============================

@app.post("/predict")
def predict(request: PromptRequest):
    if model is None or vectorizer is None:
        raise HTTPException(status_code=503, detail=MODEL_LOAD_ERROR)

    prompt = request.prompt.strip()

    if not prompt:
        raise HTTPException(status_code=400, detail="Please enter a prompt.")

    if len(prompt) > MAX_PROMPT_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt is too long. Maximum length is {MAX_PROMPT_LENGTH} characters.",
        )

    try:
        prompt_vector = vectorizer.transform([prompt])
        prediction_value = int(model.predict(prompt_vector)[0])
        probabilities = model.predict_proba(prompt_vector)[0]

        safe_probability = float(probabilities[SAFE_INDEX])
        malicious_probability = float(probabilities[MALICIOUS_INDEX])

        # Guard against NaN/inf and keep the API contract (percent, sum ~= 100).
        if not (safe_probability == safe_probability):  # NaN check
            safe_probability = 0.0
        if not (malicious_probability == malicious_probability):
            malicious_probability = 0.0
        total = safe_probability + malicious_probability
        if total <= 0:
            safe_probability, malicious_probability = 0.5, 0.5
        else:
            safe_probability /= total
            malicious_probability /= total

        prediction = "Malicious" if prediction_value == 1 else "Safe"

        explanation_data = []
        try:
            explanation = explainer.explain_instance(
                prompt,
                predict_proba,
                labels=(0, 1),
                num_features=5,
            )
            selected_label = 1 if prediction_value == 1 else 0
            for word, weight in explanation.as_list(label=selected_label):
                explanation_data.append(
                    {"word": str(word), "weight": round(float(weight), 4)}
                )
        except Exception:  # noqa: BLE001 - explanation must never break prediction
            logger.exception("LIME explanation failed")

        return {
            "prompt": prompt,
            "prediction": prediction,
            "safe_probability": round(safe_probability * 100, 2),
            "malicious_probability": round(malicious_probability * 100, 2),
            "explanation": explanation_data,
        }

    except HTTPException:
        raise

    except Exception as error:  # noqa: BLE001
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=500,
            detail="Prediction failed. Please try again later.",
        ) from error
