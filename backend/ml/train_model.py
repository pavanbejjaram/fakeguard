"""
train_model.py
══════════════
Trains on True.csv + Fake.csv from the Kaggle dataset:
  title, text, subject, date

Place files in:  backend/ml/data/True.csv
                 backend/ml/data/Fake.csv

Run:  cd backend && python ml/train_model.py
"""

import os, json, warnings, re
import numpy  as np
import pandas as pd
import joblib

from sklearn.model_selection         import train_test_split, cross_val_score
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model            import PassiveAggressiveClassifier, LogisticRegression
from sklearn.metrics                 import accuracy_score, classification_report, confusion_matrix
warnings.filterwarnings("ignore")

BASE     = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "data")
OUT_DIR  = os.path.join(BASE, "artifacts")
os.makedirs(OUT_DIR, exist_ok=True)

TRUE_CSV = os.path.join(DATA_DIR, "True.csv")
FAKE_CSV = os.path.join(DATA_DIR, "Fake.csv")


# ── Encoding fix (same as ml_predict.py) ─────────────────────────────────
ENCODING_FIXES = [
    ("â€œ",  '"'),
    ("â€",   '"'), 
    ("â€™",  "'"), 
    ("â€˜",  "'"),
 
    ("â€¦",  "…"),
    ("Ã©",   "é"), 
    ("Ã¨",   "è"), 
    ("Ã ",   "à"), 
    ("Ã¢",   "â"),
]

def fix_encoding(text: str) -> str:
    for bad, good in ENCODING_FIXES:
        text = text.replace(bad, good)
    try:
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass
    return text


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = fix_encoding(text)
    text = text.lower()
    # strip Reuters location prefix
    text = re.sub(r'^[a-z\s,]+\(reuters\)\s*[-–]\s*', '', text)
    text = re.sub(r'\(reuters\)',        ' reuters ', text)
    text = re.sub(r'http\S+',            ' ', text)
    text = re.sub(r'[^a-z0-9\s]',        ' ', text)
    text = re.sub(r'\s+',                ' ', text).strip()
    return text


def load_data():
    print("📂 Loading dataset…")

    for path, label in [(TRUE_CSV, "REAL"), (FAKE_CSV, "FAKE")]:
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"\n❌ Missing: {path}\n"
                f"   Download from Kaggle and place True.csv + Fake.csv in:\n"
                f"   {DATA_DIR}\\"
            )

    true_df = pd.read_csv(TRUE_CSV)
    fake_df = pd.read_csv(FAKE_CSV)
    true_df['label'] = 'REAL'
    fake_df['label'] = 'FAKE'

    df = pd.concat([true_df, fake_df], ignore_index=True)
    print(f"   Total rows  : {len(df):,}")
    print(f"   REAL articles: {len(true_df):,}")
    print(f"   FAKE articles: {len(fake_df):,}")

    # Combine title + text for richer signal
    df['content'] = (
        df['title'].fillna('') + ' ' +
        df['title'].fillna('') + ' ' +   # title twice → higher weight
        df['text'].fillna('')
    )
    df['content'] = df['content'].apply(clean_text)

    # Drop empty rows
    df = df[df['content'].str.len() > 30].reset_index(drop=True)
    print(f"   After cleaning: {len(df):,} rows")
    return df


def train():
    df = load_data()
    X  = df['content'].values
    y  = df['label'].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"\n   Train: {len(X_train):,}  |  Test: {len(X_test):,}")

    # ── TF-IDF ────────────────────────────────────────────────────────────
    print("\n🔢 Fitting TF-IDF vectorizer…")
    vectorizer = TfidfVectorizer(
        stop_words   = 'english',
        max_df       = 0.7,
        min_df       = 2,
        ngram_range  = (1, 2),
        max_features = 60_000,
        sublinear_tf = True,
    )
    X_train_tfidf = vectorizer.fit_transform(X_train)
    X_test_tfidf  = vectorizer.transform(X_test)

    # ── PassiveAggressiveClassifier (GeeksforGeeks approach) ──────────────
    print("🤖 Training PassiveAggressiveClassifier…")
    pac = PassiveAggressiveClassifier(C=0.3, max_iter=1000, random_state=42)
    pac.fit(X_train_tfidf, y_train)
    pac_acc = accuracy_score(y_test, pac.predict(X_test_tfidf))
    print(f"   Accuracy: {pac_acc*100:.2f}%")

    # ── Logistic Regression ───────────────────────────────────────────────
    print("🤖 Training Logistic Regression…")
    lr = LogisticRegression(C=5.0, max_iter=1000, solver='lbfgs',
                             random_state=42, class_weight='balanced')
    lr.fit(X_train_tfidf, y_train)
    lr_acc = accuracy_score(y_test, lr.predict(X_test_tfidf))
    print(f"   Accuracy: {lr_acc*100:.2f}%")

    # ── Pick best ─────────────────────────────────────────────────────────
    if lr_acc >= pac_acc:
        best, best_name, best_acc = lr,  "LogisticRegression",             lr_acc
    else:
        best, best_name, best_acc = pac, "PassiveAggressiveClassifier",    pac_acc

    y_pred = best.predict(X_test_tfidf)
    report = classification_report(y_test, y_pred, output_dict=True)
    cm     = confusion_matrix(y_test, y_pred).tolist()

    print(f"\n✅ Best model : {best_name}")
    print(f"   Test accuracy: {best_acc*100:.2f}%")
    print(f"\n{classification_report(y_test, y_pred)}")
    print(f"Confusion matrix (rows=actual, cols=predicted):")
    classes = list(best.classes_)
    print(f"   Labels: {classes}")
    print(f"   {np.array(cm)}")

    # ── Save ──────────────────────────────────────────────────────────────
    joblib.dump(vectorizer, os.path.join(OUT_DIR, "vectorizer.joblib"))
    joblib.dump(best,       os.path.join(OUT_DIR, "model.joblib"))

    metrics = {
        "model_name": best_name,
        "accuracy":   round(best_acc, 4),
        "classes":    classes,
        "report":     report,
        "confusion_matrix": cm,
    }
    with open(os.path.join(OUT_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n💾 Saved to: {OUT_DIR}")
    print("   vectorizer.joblib  model.joblib  metrics.json")
    print("\n🎉 Training complete! Restart the backend server.")


if __name__ == "__main__":
    train()
