# 🛡️ FakeGuard v2 — Full-Stack Fake News Detector
### TF-IDF + PassiveAggressiveClassifier · FastAPI · SQLite · React · Claude AI

---

## 📁 Project Structure

```
fakeguard/
├── backend/
│   ├── main.py              ← FastAPI app (all routes)
│   ├── models.py            ← SQLAlchemy ORM (User, NewsCheck tables)
│   ├── database.py          ← SQLite engine + session
│   ├── auth.py              ← bcrypt + JWT authentication
│   ├── schemas.py           ← Pydantic request/response types
│   ├── requirements.txt     ← Python dependencies
│   └── ml/
│       ├── train_model.py   ← ⭐ TRAINING SCRIPT (run this first!)
│       ├── ml_predict.py    ← Model loader + predict()
│       ├── __init__.py
│       ├── data/            ← ⭐ PUT True.csv and Fake.csv HERE
│       └── artifacts/       ← Auto-created: model.joblib, vectorizer.joblib
├── frontend/
│   ├── src/
│   │   ├── App.jsx          ← Auth + Checker pages
│   │   ├── api.js           ← All API calls
│   │   ├── index.css        ← Styles
│   │   └── main.jsx         ← Entry point
│   ├── index.html
│   ├── package.json
│   └── vite.config.js       ← Proxies /api → localhost:8000
└── README.md
```

---

## ✅ COMPLETE STEP-BY-STEP SETUP GUIDE

---

### STEP 1 — Install Prerequisites

Make sure you have these installed:

| Tool    | Version  | Download |
|---------|----------|----------|
| Python  | 3.10+    | https://python.org |
| Node.js | 18+      | https://nodejs.org |
| pip     | latest   | comes with Python |

Verify:
```bash
python --version    # should show 3.10+
node --version      # should show 18+
pip --version
```

---

### STEP 2 — Download the Kaggle Dataset

1. Go to: https://www.kaggle.com/datasets/subho117/fake-news-detection-using-machine-learning
2. Click **Download** (you'll need a free Kaggle account)
3. Unzip the downloaded file — you'll get two CSV files:
   - `True.csv`   (12,600+ real news articles from Reuters)
   - `Fake.csv`   (12,600+ fake news articles)
4. Copy both files into:

```
fakeguard/backend/ml/data/True.csv
fakeguard/backend/ml/data/Fake.csv
```

> The `data/` folder may not exist yet — create it manually if needed.

---

### STEP 3 — Install Python Backend Dependencies

Open a terminal in the `fakeguard/backend/` folder:

```bash
cd fakeguard/backend
pip install -r requirements.txt
```

This installs: fastapi, uvicorn, sqlalchemy, passlib, python-jose,
scikit-learn, numpy, pandas, joblib, httpx, nltk

---

### STEP 4 — ⭐ Train the ML Model (Important!)

This is the core step. Run the training script:

```bash
cd fakeguard/backend
python ml/train_model.py
```

**What happens:**
- Loads True.csv + Fake.csv (≈25,000 articles total)
- Cleans and combines title + article text
- Splits into 80% train / 20% test
- Fits a TF-IDF vectorizer (50,000 features, bigrams, stop-word removal)
- Trains PassiveAggressiveClassifier AND LogisticRegression
- Picks the better model automatically
- Saves to `backend/ml/artifacts/`:
  - `vectorizer.joblib`  — the fitted TF-IDF vectorizer
  - `model.joblib`       — the trained classifier
  - `metrics.json`       — accuracy score + confusion matrix

**Expected output:**
```
📂 Loading dataset…
   Total rows: 44,898  (REAL: 21,417 | FAKE: 23,481)
   Train: 35,918  |  Test: 8,980
🔢 Fitting TF-IDF vectorizer…
🤖 Training PassiveAggressiveClassifier…
   PAC accuracy:  93.20%
🤖 Training Logistic Regression…
   LR  accuracy:  98.76%
✅ Best model: LogisticRegression
   Test accuracy: 98.76%
💾 Artifacts saved!
🎉 Training complete!
```

> ✅ You should see **93–99% accuracy** depending on the dataset split.

---

### STEP 5 — Start the Backend Server

```bash
cd fakeguard/backend
uvicorn main:app --reload --port 8000
```

You should see:
```
INFO:     Started server process
INFO:     Uvicorn running on http://127.0.0.1:8000
✅ ML model loaded: LogisticRegression (98.8% accuracy)
```

Interactive API docs: http://localhost:8000/docs

---

### STEP 6 — Install Frontend Dependencies

Open a **new terminal** in `fakeguard/frontend/`:

```bash
cd fakeguard/frontend
npm install
```

---

### STEP 7 — Start the Frontend

```bash
npm run dev
```

You should see:
```
VITE v5.x  ready in 300ms
➜  Local:   http://localhost:5173/
```

---

### STEP 8 — Open the App

Open your browser at: **http://localhost:5173**

---

### STEP 9 — Register & Use the App

1. Click **Register** → create an account (username, email, password)
2. You'll be automatically logged in
3. *(Optional)* Enter your Anthropic API key from https://console.anthropic.com
   - This enables Claude AI analysis on top of ML
   - Without it, ML-only analysis still works perfectly
4. Paste any news text into the text area
5. Click **Analyze**
6. See the result:
   - 🤖 **ML Panel** — TF-IDF + Classifier prediction with probabilities
   - 🧠 **AI Panel** — Claude's semantic reasoning (if key provided)
   - ⭐ **Final Verdict** — Fused score: REAL / FAKE / UNCERTAIN
7. Click **Logout** button in the top-right to sign out

---

## 🔌 API Endpoints Reference

| Method | Endpoint              | Auth | Description |
|--------|-----------------------|------|-------------|
| POST   | `/api/auth/register`  | ❌   | Create account |
| POST   | `/api/auth/login`     | ❌   | Get JWT token |
| POST   | `/api/auth/logout`    | ✅   | Log out |
| GET    | `/api/auth/me`        | ✅   | Current user info |
| POST   | `/api/check`          | ✅   | Analyze news text |
| GET    | `/api/history`        | ✅   | Past checks |
| GET    | `/api/stats`          | ✅   | REAL/FAKE/UNCERTAIN counts |
| GET    | `/api/model-info`     | ❌   | Loaded model name + accuracy |
| POST   | `/api/reload-model`   | ✅   | Hot-reload after retraining |

---

## 🤖 How the ML Pipeline Works

```
Raw news text
     │
     ▼
clean_text()
  • lowercase
  • strip Reuters prefix ("WASHINGTON (Reuters) -")
  • remove URLs
  • keep alphanumeric only
     │
     ▼
TF-IDF Vectorizer
  • stop_words='english'
  • max_df=0.7   (ignore words in >70% of docs)
  • min_df=3     (ignore rare words)
  • ngram_range=(1,2)   (unigrams + bigrams)
  • max_features=50,000
  • sublinear_tf=True   (log normalization)
     │
     ▼
PassiveAggressiveClassifier (or LogisticRegression)
  • predict_proba() → fake_prob, real_prob
     │
     ▼
Linguistic Signal Boost
  • sensational words (+0.20 weight)
  • exclamation density (+0.08 weight)
  • ALL-CAPS ratio (+0.08 weight)
     │
     ▼
Final: FAKE / REAL / UNCERTAIN + confidence score
```

---

## ⚖️ Score Fusion (ML + AI)

When both ML and Claude AI are available:

```
combined = 0.45 × ml_score + 0.55 × ai_score

FAKE      →  combined ≤ -0.25
REAL      →  combined ≥  0.25
UNCERTAIN →  otherwise
```

Without Claude AI key: ML score used alone (weight = 1.0).

---

## 🗄️ Database Schema (SQLite)

**users** table:
- id, username, email, hashed_pw (bcrypt), created_at, is_active

**news_checks** table:
- id, user_id (FK), news_text
- ml_verdict, ml_confidence, ml_fake_prob, ml_real_prob, ml_model_name
- ai_verdict, ai_confidence, ai_summary
- final_verdict, final_score, checked_at

---

## 🔧 Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `No trained model found` | Run `python ml/train_model.py` |
| `FileNotFoundError: True.csv` | Make sure files are in `backend/ml/data/` |
| Port 8000 in use | `uvicorn main:app --port 8001` and update vite.config.js proxy |
| CORS error | Make sure backend is running on port 8000 |
| AI key error | Key must start with `sk-` — get one at console.anthropic.com |

---

## 🔒 Security Notes (before deploying)

- Change `SECRET_KEY` in `backend/auth.py`
- Add HTTPS (use nginx + certbot)
- Move API key to environment variables (`os.getenv("ANTHROPIC_KEY")`)
- For production: use PostgreSQL instead of SQLite
- Add rate limiting (slowapi) to the `/api/check` endpoint
