"""
ml_predict.py  –  fixed version
- Cleans encoding garbage (â€œ â€™ etc.) before prediction
- Lowered fake threshold from 0.60 → 0.70 to reduce false positives
- Signal boost reduced (was too aggressive on legit political news)
- Reuters/AP/CNN dateline patterns recognized as credibility signals
"""

import os, re, json
import numpy as np

BASE         = os.path.dirname(__file__)
ARTIFACT_DIR = os.path.join(BASE, "artifacts")
VECTORIZER   = os.path.join(ARTIFACT_DIR, "vectorizer.joblib")
MODEL        = os.path.join(ARTIFACT_DIR, "model.joblib")
METRICS_FILE = os.path.join(ARTIFACT_DIR, "metrics.json")


# ── Encoding fix table ────────────────────────────────────────────────────
ENCODING_FIXES = [
    ("â€œ",  '"'),   # left double quote
    ("â€",   '"'),   # right double quote (must come after â€œ)
    ("â€™",  "'"),   # right single quote / apostrophe
    ("â€˜",  "'"),   # left single quote
    ("â€¦",  "…"),   # ellipsis
    ("Ã©",   "é"),
    ("Ã¨",   "è"),
    ("Ã ",   "à"),
    ("Ã¢",   "â"),
    ("Ã®",   "î"),
    ("Ã´",   "ô"),
    ("Ã»",   "û"),
    ("â‚¬",  "€"),
]

def fix_encoding(text: str) -> str:
    """Fix common UTF-8 → Latin-1 mojibake before any other processing."""
    for bad, good in ENCODING_FIXES:
        text = text.replace(bad, good)
    # fallback: try to re-encode as latin-1 and decode as utf-8
    try:
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


# ── Credibility signals (lower fake probability) ─────────────────────────
CREDIBLE_PATTERNS = [
    r'\(reuters\)',
    r'\(ap\)',
    r'\(afp\)',
    r'\bassociated press\b',
    r'\breuters\b',
    r'\bwashington\s+\(reuters\)',
    r'\bnew york\s+\(reuters\)',
    r'\bcbs\b',
    r'\bnbc\b',
    r'\babc news\b',
    r'\bwall street journal\b',
    r'\bnew york times\b',
    r'\bthe guardian\b',
    r'\bsaid on\b',
    r'\btold reporters\b',
    r'\bspokesperson\b',
    r'\bofficial said\b',
    r'\baccording to\b',
]

# ── Sensational signals (raise fake probability) ──────────────────────────
SENSATIONAL_WORDS = {
    "shocking","bombshell","explosive","breaking","urgent","exposed",
    "cover-up","coverup","deep state","cabal","whistleblower",
    "deleted","banned","censored","hoax","miracle cure",
    "they don't want","secret agenda","globalist","illuminati",
    "false flag","crisis actor","plandemic","scamdemic",
}


def _credibility_discount(text: str) -> float:
    """Returns a value to SUBTRACT from fake_prob for credible sourcing."""
    t = text.lower()
    hits = sum(1 for p in CREDIBLE_PATTERNS if re.search(p, t))
    return min(hits * 0.06, 0.25)   # up to -0.25 for highly sourced text


def _sensational_boost(text: str) -> float:
    """Returns a value to ADD to fake_prob for sensational language."""
    words = set(text.lower().split())
    hits  = len(words & SENSATIONAL_WORDS)
    excl  = min(text.count('!') / max(len(text.split()), 1) * 10, 1.0)
    caps_letters = [c for c in text if c.isalpha()]
    caps  = sum(1 for c in caps_letters if c.isupper()) / max(len(caps_letters), 1)
    # only penalize if clearly excessive (>30% caps is suspicious)
    caps_boost = max(caps - 0.30, 0) * 0.3
    return min(hits * 0.04 + excl * 0.06 + caps_boost, 0.20)


# ── Text cleaning (must match train_model.py) ─────────────────────────────
def clean_text(text: str) -> str:
    text = fix_encoding(text)
    text = text.lower()
    text = re.sub(r'^[A-Z\s]+\(reuters\)\s*[-–]\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'http\S+',     ' ', text)
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+',          ' ', text).strip()
    return text


# ── Fallback (before training) ────────────────────────────────────────────
class FallbackModel:
    def predict(self, text: str) -> dict:
        boost    = _sensational_boost(text)
        discount = _credibility_discount(text)
        fake_prob = min(max(0.40 + boost - discount, 0.01), 0.99)
        real_prob = 1.0 - fake_prob
        if fake_prob > 0.70:
            verdict, conf = "FAKE", fake_prob
        elif real_prob > 0.70:
            verdict, conf = "REAL", real_prob
        else:
            verdict, conf = "UNCERTAIN", max(fake_prob, real_prob)
        return {
            "verdict": verdict, "confidence": round(conf, 4),
            "fake_prob": round(fake_prob, 4), "real_prob": round(real_prob, 4),
            "model": "fallback (run python ml/train_model.py)",
            "signals": {"boost": round(boost, 4), "discount": round(discount, 4)},
        }


# ── Trained model ─────────────────────────────────────────────────────────
class TrainedModel:
    def __init__(self):
        import joblib
        self.vec      = joblib.load(VECTORIZER)
        self.clf      = joblib.load(MODEL)
        self.classes  = list(self.clf.classes_)
        with open(METRICS_FILE) as f:
            m = json.load(f)
        self.model_name = m.get("model_name", "unknown")
        self.accuracy   = m.get("accuracy",   0.0)

    def predict(self, text: str) -> dict:
        # Fix encoding BEFORE cleaning
        fixed   = fix_encoding(text)
        cleaned = clean_text(fixed)
        vec     = self.vec.transform([cleaned])

        if hasattr(self.clf, 'predict_proba'):
            proba = self.clf.predict_proba(vec)[0]
        else:
            # PassiveAggressiveClassifier: use decision_function → sigmoid
            decision  = self.clf.decision_function(vec)[0]
            prob_fake = float(1.0 / (1.0 + np.exp(-decision)))
            proba_map = {}
            for cls in self.classes:
                proba_map[cls] = prob_fake if cls == 'FAKE' else 1.0 - prob_fake
            proba = np.array([proba_map[c] for c in self.classes])

        fake_idx  = self.classes.index('FAKE')
        real_idx  = self.classes.index('REAL')
        fake_prob = float(proba[fake_idx])
        real_prob = float(proba[real_idx])

        # Apply credibility discount and sensational boost
        boost    = _sensational_boost(fixed)          # use original text for signals
        discount = _credibility_discount(fixed)

        fake_adj = min(max(fake_prob + boost - discount, 0.01), 0.99)
        real_adj = 1.0 - fake_adj

        # ── Verdict thresholds (raised to 0.70 to reduce false positives) ──
        if fake_adj > 0.70:
            verdict, conf = "FAKE", fake_adj
        elif real_adj > 0.70:
            verdict, conf = "REAL", real_adj
        else:
            verdict, conf = "UNCERTAIN", max(fake_adj, real_adj)

        return {
            "verdict":    verdict,
            "confidence": round(conf, 4),
            "fake_prob":  round(fake_adj, 4),
            "real_prob":  round(real_adj, 4),
            "model":      f"{self.model_name} ({self.accuracy*100:.1f}% accuracy)",
            "signals": {
                "boost":    round(boost, 4),
                "discount": round(discount, 4),
            },
        }


# ── Singleton ─────────────────────────────────────────────────────────────
_instance = None

def get_model():
    global _instance
    if _instance is None:
        if os.path.exists(VECTORIZER) and os.path.exists(MODEL):
            try:
                _instance = TrainedModel()
                print(f"✅ ML model loaded: {_instance.model_name} "
                      f"({_instance.accuracy*100:.1f}% accuracy)")
            except Exception as e:
                print(f"⚠️  Could not load ML model: {e}. Using fallback.")
                _instance = FallbackModel()
        else:
            print("⚠️  No trained model found. Run: python ml/train_model.py")
            _instance = FallbackModel()
    return _instance


def predict(text: str) -> dict:
    return get_model().predict(text)


def reload_model():
    global _instance
    _instance = None
    return get_model()
