#!/usr/bin/env python3
import json
import gzip
import os
import subprocess
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Import scoring functions from rank
from rank import calculate_score, generate_reasoning, TARGET_DATE, ROLE_CONFIGS

app = FastAPI(title="Redrob Candidate Ranker Dashboard")

# Global state to hold candidates and pre-computed ranks per role
CANDIDATES = []
SCORED_LISTS = {}
HONEYPOT_LISTS = {}
ROLE_STATS = {}

def load_data():
    global CANDIDATES, SCORED_LISTS, HONEYPOT_LISTS, ROLE_STATS
    candidates_path = "./candidates.jsonl"
    
    if not os.path.exists(candidates_path):
        if os.path.exists(candidates_path + ".gz"):
            candidates_path = candidates_path + ".gz"
        else:
            print("Error: candidates.jsonl or candidates.jsonl.gz not found!")
            return
            
    print(f"Loading data from {candidates_path}...")
    start_time = datetime.now()
    
    cands = []
    open_func = gzip.open if candidates_path.endswith(".gz") else open
    mode = "rt" if candidates_path.endswith(".gz") else "r"
    
    with open_func(candidates_path, mode, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cands.append(json.loads(line))
                
    CANDIDATES = cands
    
    # Initialize lists
    for role_name in ROLE_CONFIGS.keys():
        SCORED_LISTS[role_name] = []
        HONEYPOT_LISTS[role_name] = []
        ROLE_STATS[role_name] = {}
        
    print(f"Loaded {len(CANDIDATES)} candidates. Pre-scoring for all roles...")
    
    # Pre-score for each role
    for role_name in ROLE_CONFIGS.keys():
        role_start = datetime.now()
        scored = []
        honeypots = []
        
        for cand in CANDIDATES:
            score, data = calculate_score(cand, role_name)
            if score == -1000.0:
                honeypots.append({
                    "candidate_id": cand["candidate_id"],
                    "profile": cand["profile"],
                    "redrob_signals": cand["redrob_signals"],
                    "career_history": cand["career_history"],
                    "skills": cand["skills"],
                    "honeypot_reason": data,
                    "score": 0.0,
                    "is_honeypot": True
                })
            else:
                scored.append({
                    "candidate_id": cand["candidate_id"],
                    "profile": cand["profile"],
                    "redrob_signals": cand["redrob_signals"],
                    "career_history": cand["career_history"],
                    "skills": cand["skills"],
                    "score": score,
                    "matched_skills": data,
                    "is_honeypot": False
                })
                
        # Sort to establish rank
        scored.sort(key=lambda x: (-x["score"], x["candidate_id"]))
        for i, item in enumerate(scored):
            item["rank"] = i + 1
            item["reasoning"] = generate_reasoning(item, i + 1, item["score"], item["matched_skills"], role_name)
            
        SCORED_LISTS[role_name] = scored
        HONEYPOT_LISTS[role_name] = honeypots
        
        # Calculate stats for this role
        exp_list = [c["profile"].get("years_of_experience", 0.0) for c in scored]
        avg_exp = sum(exp_list) / len(exp_list) if exp_list else 0
        max_score = scored[0]["score"] if scored else 0.0
        
        work_modes = {}
        for c in scored:
            mode_pref = c["redrob_signals"].get("preferred_work_mode", "unknown")
            work_modes[mode_pref] = work_modes.get(mode_pref, 0) + 1
            
        notice_periods = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
        for c in scored:
            notice = c["redrob_signals"].get("notice_period_days", 90)
            if notice <= 30:
                notice_periods["0-30"] += 1
            elif notice <= 60:
                notice_periods["31-60"] += 1
            elif notice <= 90:
                notice_periods["61-90"] += 1
            else:
                notice_periods["90+"] += 1
                
        reloc_willing = sum(1 for c in scored if c["redrob_signals"].get("willing_to_relocate", False))
        reloc_rate = (reloc_willing / len(scored)) * 100 if scored else 0
        
        ROLE_STATS[role_name] = {
            "total_pool": len(CANDIDATES),
            "valid_count": len(scored),
            "honeypot_count": len(honeypots),
            "avg_experience": round(avg_exp, 1),
            "max_score": round(max_score, 4),
            "work_modes": work_modes,
            "notice_periods": notice_periods,
            "relocation_rate": round(reloc_rate, 1)
        }
        
        role_dur = (datetime.now() - role_start).total_seconds()
        print(f"  Scored {role_name} in {role_dur:.2f} seconds.")
        
    duration = (datetime.now() - start_time).total_seconds()
    print(f"Loaded and pre-scored all roles in {duration:.2f} seconds.")

# Load the data on startup
@app.on_event("startup")
def startup_event():
    load_data()

@app.get("/api/stats")
def get_stats(role: str = Query("Senior AI Engineer")):
    if role not in ROLE_STATS:
        raise HTTPException(status_code=400, detail=f"Invalid role name. Must be one of: {list(ROLE_CONFIGS.keys())}")
    return ROLE_STATS[role]

@app.get("/api/candidates")
def get_candidates(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("rank"),
    order: str = Query("asc"),
    search: Optional[str] = None,
    min_exp: Optional[float] = None,
    max_exp: Optional[float] = None,
    work_mode: Optional[str] = None,
    exclude_honeypots: bool = Query(True),
    role: str = Query("Senior AI Engineer")
):
    if role not in ROLE_CONFIGS:
        raise HTTPException(status_code=400, detail="Invalid role name")
        
    scored_list = SCORED_LISTS[role]
    honeypot_list = HONEYPOT_LISTS[role]
    
    source = scored_list if exclude_honeypots else (scored_list + honeypot_list)
    
    filtered = source
    
    # 1. Search text filter
    if search:
        search = search.lower()
        res = []
        for c in filtered:
            name = c["profile"].get("anonymized_name", "").lower()
            headline = c["profile"].get("headline", "").lower()
            summary = c["profile"].get("summary", "").lower()
            current_title = c["profile"].get("current_title", "").lower()
            current_company = c["profile"].get("current_company", "").lower()
            skills_str = " ".join([s.get("name", "").lower() for s in c.get("skills", [])])
            
            if (search in name or search in headline or search in summary or 
                search in current_title or search in current_company or search in skills_str):
                res.append(c)
        filtered = res
        
    # 2. Experience bounds
    if min_exp is not None:
        filtered = [c for c in filtered if c["profile"].get("years_of_experience", 0.0) >= min_exp]
    if max_exp is not None:
        filtered = [c for c in filtered if c["profile"].get("years_of_experience", 0.0) <= max_exp]
        
    # 3. Work mode
    if work_mode and work_mode != "all":
        filtered = [c for c in filtered if c["redrob_signals"].get("preferred_work_mode", "").lower() == work_mode.lower()]
        
    # 4. Sorting
    reverse_sort = (order == "desc")
    if sort_by == "rank":
        filtered.sort(key=lambda x: x.get("rank", 999999), reverse=reverse_sort)
    elif sort_by == "score":
        filtered.sort(key=lambda x: x.get("score", 0.0), reverse=reverse_sort)
    elif sort_by == "experience":
        filtered.sort(key=lambda x: x["profile"].get("years_of_experience", 0.0), reverse=reverse_sort)
    elif sort_by == "notice_period":
        filtered.sort(key=lambda x: x["redrob_signals"].get("notice_period_days", 90), reverse=reverse_sort)
    elif sort_by == "response_rate":
        filtered.sort(key=lambda x: x["redrob_signals"].get("recruiter_response_rate", 0.0), reverse=reverse_sort)
    elif sort_by == "connections":
        filtered.sort(key=lambda x: x["redrob_signals"].get("connection_count", 0), reverse=reverse_sort)
    elif sort_by == "github":
        filtered.sort(key=lambda x: x["redrob_signals"].get("github_activity_score", -1), reverse=reverse_sort)
        
    # Paginate
    total_count = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated = filtered[start_idx:end_idx]
    
    results = []
    for c in paginated:
        results.append({
            "candidate_id": c["candidate_id"],
            "rank": c.get("rank"),
            "score": c["score"],
            "name": c["profile"].get("anonymized_name"),
            "headline": c["profile"].get("headline"),
            "current_title": c["profile"].get("current_title"),
            "current_company": c["profile"].get("current_company"),
            "location": c["profile"].get("location"),
            "years_of_experience": c["profile"].get("years_of_experience"),
            "is_honeypot": c.get("is_honeypot", False),
            "honeypot_reason": c.get("honeypot_reason"),
            "notice_period_days": c["redrob_signals"].get("notice_period_days"),
            "recruiter_response_rate": c["redrob_signals"].get("recruiter_response_rate"),
            "preferred_work_mode": c["redrob_signals"].get("preferred_work_mode")
        })
        
    return {
        "total": total_count,
        "page": page,
        "limit": limit,
        "candidates": results
    }

@app.get("/api/candidates/{candidate_id}")
def get_candidate_detail(candidate_id: str, role: str = Query("Senior AI Engineer")):
    if role not in ROLE_CONFIGS:
        raise HTTPException(status_code=400, detail="Invalid role name")
        
    # Search scored list
    for c in SCORED_LISTS[role]:
        if c["candidate_id"] == candidate_id:
            return c
    # Search honeypots
    for c in HONEYPOT_LISTS[role]:
        if c["candidate_id"] == candidate_id:
            return c
            
    raise HTTPException(status_code=404, detail="Candidate not found")

@app.post("/api/generate")
def generate_submission(role: str = Query("Senior AI Engineer")):
    if role not in ROLE_CONFIGS:
        raise HTTPException(status_code=400, detail="Invalid role name")
        
    try:
        # Run the ranker subprocess with role argument
        cmd = ["python3", "rank.py", "--candidates", "./candidates.jsonl", "--out", "./submission.csv", "--role", role]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Run the validator subprocess
        val_cmd = ["python3", "validate_submission.py", "submission.csv"]
        val_res = subprocess.run(val_cmd, capture_output=True, text=True)
        
        is_valid = (val_res.returncode == 0)
        
        return {
            "success": True,
            "ranker_output": res.stdout,
            "validator_output": val_res.stdout if is_valid else val_res.stderr,
            "is_valid": is_valid
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

# Serve the static files
os.makedirs("static", exist_ok=True)

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
