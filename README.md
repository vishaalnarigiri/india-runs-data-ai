# Intelligent Candidate Discovery & Ranking Challenge

This repository contains the candidate ranker engine and the Recruitment Discovery Dashboard built for the Redrob AI Senior AI Engineer founding team match challenge.

The solution features a fast, offline heuristic scoring system that parses 100,000 candidate profiles, identifies and filters out honeypot anomalies, ranks candidates deterministically, and generates detailed reasoning explanations.

## 🛠 Setup & Installation

To install all dependencies:

```bash
pip install -r requirements.txt
```

Ensure `candidates.jsonl` (or its gzipped version `candidates.jsonl.gz`) is present in this directory.

## 🚀 Reproducing the Submission CSV

Run the following command to rank candidates and write the output `submission.csv` containing the top 100 fits:

```bash
python3 rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

### Format Validation
To run the official validator check:

```bash
python3 validate_submission.py submission.csv
```

## 🖥 Recruitment Discovery Dashboard

We built a beautiful, bright-themed Single Page Web Application (SPA) designed to help recruiters browse the scored candidate pool, filter by work preference and experience bounds, dynamically sort by multiple platform signals, and run/validate the ranking pipeline.

To start the local FastAPI web server:

```bash
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Once running, navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser.

## 🔍 Scoring Methodology & Honeypot Filtering

### 1. Match Scoring
Candidates are evaluated on a 4-part base score (max 100 pts) based on the JD requirements:
- **Title Fit (25 pts)**: Scoring based on titles containing target keywords (e.g. AI/ML Engineer, NLP, Retrieval, Software Engineer) vs non-technical roles.
- **Experience Match (20 pts)**: Targets 5-9 years experience, applying penalties outside this band.
- **Skill Alignment (30 pts)**: Matches vector database keywords (Pinecone, FAISS, Milvus) and retrieval frameworks weighted by proficiency and usage duration.
- **Employer Profile (25 pts)**: Extra points for product company histories (OpenAI, Google, Microsoft, Amazon) and penalties for service-only consulting histories.

This base score is modulated by a **Behavioral Multiplier** (ranging from 0.4 to 1.35) using Redrob engagement metrics: recruiter response rates, login recency, notice period, location/relocation preferences, and GitHub contributions.

### 2. Honeypot Filters
We identify and block all ~80 honeypots dynamically to prevent them from reaching the top 100 (assigning them a score of `-1000`):
- **Modern Startup Mismatches**: Flagging candidates claiming experience at modern AI startups (Krutrim, Sarvam AI) before their founding year (2023).
- **Skill Duration Typos**: Catching profiles claiming "expert" or "advanced" proficiency in 5+ skills with 0 months of usage.
- **Experience Gap anomalies**: Filtering candidates where the profile's stated years of experience deviates from the actual sum of career history durations by more than 5 years.
