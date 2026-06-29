# Intelligent Candidate Ranking — Redrob Hackathon

This repository contains the candidate ranking AI designed to find the top 100 candidates for the **Senior AI Engineer — Founding Team** role at Redrob AI.

## 🚀 Reproduction Command

To reproduce the submission file `submission.csv` from the 100k candidate pool, run the following command in your terminal. This command runs end-to-end on CPU in **~10 seconds**, well within the 5-minute constraint.

```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

## 🛠️ Setup & Installation

Ensure you have Python 3.8+ installed, then install the dependencies:

```bash
pip install -r requirements.txt
```

## 📐 2-Stage Pipeline Architecture

To handle the trade-off between recall, latency, and profile authenticity, our system uses a **2-stage pipeline**:

### Stage 1: Retrieval & Filtering
- **Honeypot Exclusion**: Evaluates candidates for logical inconsistencies (impossible job durations, zero-duration skills, YOE vs history mismatches) and automatically excludes exactly 65 honeypot trap candidates.
- **Role/Title Exclusion**: Excludes generic keyword-stuffers (like HR/Marketing Managers with AI keywords) who lack any software/data/ML background.
- **Heuristic Selection**: Ranks candidates based on current title, years of experience, and core AI/ML skill matches to narrow down the pool of 100,000 to the top 2,000.

### Stage 2: Deep Scoring & Re-ranking
- **Disqualifiers Check**:
  - Excludes candidates whose entire career history consists *only* of outsourcing/IT services firms (TCS, Infosys, Wipro, etc.).
  - Excludes candidates with academic research-only experience or CV/Speech-only skills without NLP/IR exposure.
- **Detailed Scoring (Weighted)**:
  - *Title Fit (25%)*: Ranks core AI/ML titles highest.
  - *Skills Fit (25%)*: Evaluates core search, retrieval, and NLP skills based on proficiency, duration, and endorsements.
  - *Experience Quality (20%)*: Scores for the 5-9 years sweet spot and product company/startup history.
  - *Logistics & Location (10%)*: Scores Pune/Noida location and short notice periods.
- **Behavioral Signal Modifier (20% Multiplicative)**: Applies a multiplier based on recruiter response rates, login recency, and GitHub activity scores.
- **Deterministic Tiebreaking**: Automatically resolves score ties alphabetically by candidate ID.

## 📦 Sandbox App (HuggingFace Spaces)
The sandbox interface is defined in `app.py`. To run the sandbox locally:
```bash
streamlit run app.py
```
