"""
src/pipeline.py  –  SkillMatch ML Pipeline  (v2 – scored + explainable)

Changes from v1:
  - Returns top-3 predicted roles with confidence scores (probabilities)
  - Computes skill overlap % between user input and each predicted role
  - Returns a natural-language "why" explanation for each match
  - `integretion()` still works (backward-compatible) via predict_single()
"""

import pandas as pd
import sys, os, pickle, re
import warnings

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import config
from src.cleaner import clean_data, remove_punctuation, clean_data1, clean_data2
from src.logging_file import get_log
from sklearn.exceptions import InconsistentVersionWarning

logger = get_log()

warnings.filterwarnings("ignore", category=InconsistentVersionWarning)

# ── Load artefacts once at import time ────────────────────────────────────────
try:
    model         = pickle.load(open(config.model_path,         "rb"))
    vectorizer    = pickle.load(open(config.vectorizer_path,    "rb"))
    label_encoder = pickle.load(open(config.label_encoder_path, "rb"))
except Exception as e:
    logger.error(f"Failed to load ML artefacts: {e}")
    raise


# ── Skill keyword bank per role  (extend as needed) ───────────────────────────
ROLE_SKILLS: dict[str, list[str]] = {
    "data scientist":        ["python", "machine learning", "statistics", "pandas", "numpy",
                               "scikit-learn", "tensorflow", "deep learning", "sql", "r"],
    "data analyst":          ["sql", "excel", "power bi", "tableau", "python", "pandas",
                               "statistics", "reporting", "visualization"],
    "software engineer":     ["python", "java", "c++", "javascript", "typescript", "git",
                               "algorithms", "data structures", "api", "docker"],
    "machine learning engineer": ["python", "tensorflow", "pytorch", "mlops", "docker",
                                   "kubernetes", "scikit-learn", "model deployment", "apis"],
    "web developer":         ["html", "css", "javascript", "react", "node", "typescript",
                               "rest api", "git", "sql"],
    "backend developer":     ["python", "java", "node", "django", "flask", "fastapi",
                               "sql", "postgresql", "redis", "docker", "apis"],
    "frontend developer":    ["react", "vue", "angular", "javascript", "typescript",
                               "html", "css", "tailwind", "git"],
    "devops engineer":       ["docker", "kubernetes", "aws", "linux", "terraform",
                               "ci/cd", "jenkins", "bash", "monitoring"],
    "product manager":       ["roadmap", "agile", "stakeholder", "jira", "analytics",
                               "user research", "strategy", "sql"],
    "business analyst":      ["sql", "excel", "requirements", "stakeholder", "process",
                               "jira", "power bi", "documentation"],
}


def _clean_text(text: str) -> str:
    """Run the full cleaning pipeline and return a single cleaned string."""
    if isinstance(text, list):
        text = text[0]
    text = str(text)
    df = pd.DataFrame({"skills": [text]})
    x  = clean_data(df)
    x  = remove_punctuation(x)
    x  = clean_data1(x)
    x  = clean_data2(x)
    return x[0]


def _skill_overlap(user_text: str, role: str) -> tuple[int, list[str]]:
    """
    Returns (overlap_percent, matched_keywords) for a given role.
    Simple keyword matching – fast and explainable.
    """
    role_key      = role.lower()
    keywords      = ROLE_SKILLS.get(role_key, [])
    if not keywords:
        # generic fallback: look for any tech word in common list
        keywords = ["python", "sql", "javascript", "java", "c++", "aws",
                    "docker", "machine learning", "data", "api"]

    user_lower    = user_text.lower()
    matched       = [kw for kw in keywords if kw in user_lower]
    pct           = int(round(len(matched) / max(len(keywords), 1) * 100))
    return pct, matched


def _why_explanation(role: str, matched: list[str], score_pct: int, overlap_pct: int) -> str:
    """Generate a concise natural-language explanation."""
    if not matched:
        return (
            f"Your overall skill profile closely matches the patterns of a {role.title()} "
            f"based on our ML model ({score_pct:.0f}% confidence)."
        )

    matched_str = ", ".join(f"**{m}**" for m in matched[:4])
    tail        = f" and {len(matched) - 4} more" if len(matched) > 4 else ""
    return (
        f"Your skills in {matched_str}{tail} align strongly with {role.title()} requirements. "
        f"Skill keyword overlap: {overlap_pct}%. Model confidence: {score_pct:.0f}%."
    )


def predict_scored(text: str, top_n: int = 3) -> list[dict]:
    """
    Returns a list of up to `top_n` dicts:
      {
        "rank":          1,
        "role":          "Data Scientist",
        "confidence":    87,          # model probability × 100
        "skill_overlap": 60,          # keyword overlap %
        "matched_skills": ["python", "pandas", ...],
        "explanation":   "Your skills in python, pandas..."
      }
    """
    cleaned   = _clean_text(text)
    vector    = vectorizer.transform([cleaned])

    # Get class probabilities if available, else use decision function
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(vector)[0]
    else:
        # SVM / LinearSVC: use decision_function, softmax-normalise
        raw   = model.decision_function(vector)[0]
        e     = [2.718281828 ** float(v) for v in raw]
        s     = sum(e)
        probs = [v / s for v in e]

    # Top-N indices sorted by descending probability
    top_indices = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)[:top_n]

    results = []
    for rank, idx in enumerate(top_indices, start=1):
        role         = label_encoder.inverse_transform([idx])[0]
        confidence   = int(round(float(probs[idx]) * 100))
        overlap, matched = _skill_overlap(text, role)
        explanation  = _why_explanation(role, matched, confidence, overlap)

        results.append({
            "rank":           rank,
            "role":           role,
            "confidence":     confidence,
            "skill_overlap":  overlap,
            "matched_skills": matched,
            "explanation":    explanation,
        })

    return results


# ── Backward-compatible single-string wrapper ─────────────────────────────────
def integretion(text) -> str:
    """Legacy API — returns top predicted role as a plain string."""
    results = predict_scored(text, top_n=1)
    return results[0]["role"] if results else "Unknown"
