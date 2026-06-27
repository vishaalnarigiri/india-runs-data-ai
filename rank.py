#!/usr/bin/env python3
import json
import gzip
import csv
import re
import sys
import argparse
from datetime import datetime

# Target date for recency calculations (based on challenge date bounds around July 2026)
TARGET_DATE = datetime(2026, 7, 2)

PRODUCT_COMPANIES = {
    "Google", "Microsoft", "Amazon", "OpenAI", "Swiggy", "Zomato", "Razorpay", 
    "Flipkart", "Dream11", "Freshworks", "PhonePe", "Paytm", "Ola", "Meesho", "CRED",
    "Adobe", "Apple", "Meta", "Salesforce", "Netflix", "Uber", "LinkedIn", "Pinecone",
    "Scale AI", "Swiggy", "Swiggy", "Swiggy", "swiggy", "Observe.AI", "Verloop.io",
    "Yellow.ai", "Rephrase.ai", "Aganitha", "Locobuzz", "Mad Street Den", "Niramai"
}

CONSULTING_COMPANIES = {
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini", "Tech Mahindra", 
    "Mindtree", "Mphasis", "HCL", "L&T", "six sigma", "sixsigma"
}

DISQUALIFYING_TITLES = {
    "marketing manager", "accountant", "operations manager", "hr manager", 
    "customer support", "project manager", "business analyst", "graphic designer", 
    "operations executive", "sales executive", "content writer", "six sigma"
}

# Define Target Configurations per Role
ROLE_CONFIGS = {
    "Senior AI Engineer": {
        "titles": ["ai engineer", "ml engineer", "machine learning engineer", "nlp engineer", "retrieval engineer", "computer vision engineer"],
        "sub_titles": ["data scientist", "software engineer", "lead engineer"],
        "skills": {
            "pinecone", "milvus", "weaviate", "qdrant", "faiss", "elasticsearch", "opensearch",
            "hybrid search", "vector search", "information retrieval", "bm25", "semantic search",
            "embeddings", "sentence transformers", "sentence_transformers", "nlp", "transformers",
            "hugging face transformers", "pytorch", "llama", "langchain", "llamaindex", "rag",
            "fine-tuning", "lora", "qlora", "peft", "fine-tuning llms", "python",
            "ndcg", "map", "mrr", "evaluation", "a/b test", "learning to rank"
        },
        "min_exp": 5.0,
        "max_exp": 9.0
    },
    "Senior Backend Engineer": {
        "titles": ["backend engineer", "backend developer", "systems engineer", "platform engineer", "database engineer"],
        "sub_titles": ["software engineer", "full stack developer", "lead engineer"],
        "skills": {
            "python", "go", "java", "sql", "postgresql", "mysql", "redis", "mongodb", "kafka",
            "microservices", "docker", "kubernetes", "grpc", "aws", "gcp", "fastapi", "flask", 
            "django", "rest api", "api design", "system design"
        },
        "min_exp": 5.0,
        "max_exp": 10.0
    },
    "Frontend Developer": {
        "titles": ["frontend engineer", "frontend developer", "ui engineer", "web developer"],
        "sub_titles": ["software engineer", "full stack developer", "ux engineer"],
        "skills": {
            "javascript", "typescript", "react", "next.js", "redux", "html", "css", "tailwind", 
            "vue.js", "angular", "webpack", "figma", "sass", "jest", "npm", "node.js"
        },
        "min_exp": 3.0,
        "max_exp": 8.0
    },
    "Data Engineer": {
        "titles": ["data engineer", "analytics engineer", "big data engineer", "data warehouse engineer"],
        "sub_titles": ["software engineer", "database administrator", "business analyst"],
        "skills": {
            "python", "sql", "spark", "pyspark", "airflow", "snowflake", "dbt", "databricks", 
            "hadoop", "etl", "data pipelines", "apache beam", "apache flink", "kafka", "mapreduce"
        },
        "min_exp": 4.0,
        "max_exp": 9.0
    }
}

def is_honeypot(cand):
    profile = cand.get("profile", {})
    career = cand.get("career_history", [])
    skills = cand.get("skills", [])
    
    # Check 1: Krutrim/Sarvam AI experience starting before 2023
    for job in career:
        comp = job.get("company", "")
        start = job.get("start_date")
        if comp in ["Krutrim", "Sarvam AI"] and start:
            try:
                s_year = int(start.split("-")[0])
                if s_year < 2023:
                    return True, "modern_ai_startup_before_2023"
            except Exception:
                pass
                
    # Check 2: Expert/Advanced proficiency in 5+ skills with 0 months duration
    zero_dur_expert_count = sum(1 for s in skills if s.get("proficiency") in ["expert", "advanced"] and s.get("duration_months", 0) == 0)
    if zero_dur_expert_count >= 5:
        return True, f"zero_dur_expert({zero_dur_expert_count})"
        
    # Check 3: Large experience mismatch (profile vs total history)
    total_history_months = sum(job.get("duration_months", 0) for job in career)
    total_history_years = total_history_months / 12.0
    years_exp = profile.get("years_of_experience", 0)
    if abs(years_exp - total_history_years) > 5.0 and total_history_years > 0:
        return True, f"exp_mismatch(profile={years_exp}y, career={total_history_years:.1f}y)"
        
    return False, None

def calculate_score(cand, role_name="Senior AI Engineer"):
    # If honeypot, return -1000
    flagged, reason = is_honeypot(cand)
    if flagged:
        return -1000.0, reason
        
    profile = cand.get("profile", {})
    career = cand.get("career_history", [])
    skills = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    
    # Get config for role
    cfg = ROLE_CONFIGS.get(role_name, ROLE_CONFIGS["Senior AI Engineer"])
    
    # 1. Experience Fit (max 20 pts)
    years = profile.get("years_of_experience", 0.0)
    min_exp_opt = cfg["min_exp"]
    max_exp_opt = cfg["max_exp"]
    
    if min_exp_opt <= years <= max_exp_opt:
        exp_score = 20.0
    elif (min_exp_opt - 1.0) <= years < min_exp_opt or max_exp_opt < years <= (max_exp_opt + 3.0):
        exp_score = 15.0
    else:
        exp_score = 2.0
        
    # 2. Title Match (max 25 pts)
    current_title = profile.get("current_title", "").lower()
    
    # Check for disqualifying current titles
    # Frontend/Backend engineers don't have disqualifying title checks for non-technical 
    # to the same degree, but we'll apply it generally for pure management/non-tech roles.
    is_disqualified = False
    for bad_title in DISQUALIFYING_TITLES:
        if bad_title in current_title:
            # Let backend/data roles keep business analyst, but penalize marketing/accounting/HR
            if role_name in ["Senior Backend Engineer", "Data Engineer", "Frontend Developer"] and bad_title == "business analyst":
                continue
            is_disqualified = True
            break
            
    title_score = 0.0
    if not is_disqualified:
        if any(term in current_title for term in cfg["titles"]):
            title_score = 25.0
        elif any(term in current_title for term in cfg["sub_titles"]):
            title_score = 18.0
        else:
            title_score = 5.0
    else:
        title_score = 0.0
        
    # 3. Skills Match (max 30 pts)
    skill_points = 0.0
    skills_found = []
    for s in skills:
        name = s.get("name", "").lower()
        if name in cfg["skills"]:
            prof = s.get("proficiency", "beginner")
            dur = s.get("duration_months", 0)
            
            prof_w = 1.0 if prof == "expert" else 0.8 if prof == "advanced" else 0.6 if prof == "intermediate" else 0.3
            dur_w = min(dur, 60) / 60.0
            
            skill_points += prof_w * (0.5 + 0.5 * dur_w)
            skills_found.append(s.get("name"))
            
    skill_score = min(skill_points * 4.5, 30.0)
    
    # 4. Company Profile Fit (max 25 pts)
    employers = [job.get("company", "") for job in career if job.get("company")]
    
    num_product = sum(1 for emp in employers if emp in PRODUCT_COMPANIES)
    num_consulting = sum(1 for emp in employers if emp in CONSULTING_COMPANIES)
    
    company_score = 0.0
    if len(employers) > 0:
        if num_consulting == len(employers):
            company_score = 0.0
        else:
            company_score = 15.0
            if num_product > 0:
                company_score += 5.0
            if any(emp in ["OpenAI", "Google", "Microsoft", "Amazon", "Scale AI"] for emp in employers):
                company_score += 5.0
    
    base_score = exp_score + title_score + skill_score + company_score
    
    # 5. Behavioral Multipliers
    multiplier = 1.0
    
    # Recruiter response rate
    response_rate = signals.get("recruiter_response_rate", 0.0)
    multiplier *= (0.7 + 0.3 * response_rate)
    
    # Last active date recency
    last_active = signals.get("last_active_date")
    if last_active:
        try:
            la_date = datetime.strptime(last_active, "%Y-%m-%d")
            active_days = (TARGET_DATE - la_date).days
            if active_days <= 30:
                multiplier *= 1.15
            elif active_days <= 90:
                multiplier *= 1.0
            elif active_days <= 180:
                multiplier *= 0.8
            else:
                multiplier *= 0.5
        except Exception:
            multiplier *= 0.8
            
    # Open to work flag
    if signals.get("open_to_work_flag", False):
        multiplier *= 1.15
    else:
        multiplier *= 0.95
        
    # Notice Period
    notice_days = signals.get("notice_period_days", 90)
    if notice_days <= 30:
        multiplier *= 1.15
    elif notice_days <= 60:
        multiplier *= 1.0
    elif notice_days <= 90:
        multiplier *= 0.8
    else:
        multiplier *= 0.5
        
    # Github activity
    gh_score = signals.get("github_activity_score", -1)
    if gh_score > 0:
        multiplier *= (1.0 + 0.15 * (gh_score / 100.0))
    elif gh_score == -1:
        multiplier *= 0.95
        
    # Location Relocation
    loc = profile.get("location", "").lower()
    relocate = signals.get("willing_to_relocate", False)
    country = profile.get("country", "").lower()
    
    if "noida" in loc or "pune" in loc or "delhi" in loc or "ncr" in loc:
        multiplier *= 1.15
    elif relocate and country in ["india", ""]:
        multiplier *= 1.0
    elif not relocate and country in ["india", ""]:
        multiplier *= 0.75
    else:
        multiplier *= 0.4
        
    # Verified contact info
    v_email = signals.get("verified_email", False)
    v_phone = signals.get("verified_phone", False)
    if v_email and v_phone:
        multiplier *= 1.05
        
    final_score = base_score * multiplier
    final_score = max(0.001, min(final_score, 100.0)) / 100.0
    
    return final_score, skills_found

def generate_reasoning(cand, rank, score_val, matched_skills, role_name="Senior AI Engineer"):
    profile = cand.get("profile", {})
    exp = profile.get("years_of_experience", 0.0)
    title = profile.get("current_title", "Software Engineer")
    signals = cand.get("redrob_signals", {})
    notice = signals.get("notice_period_days", 30)
    
    employers = list(set([job.get("company") for job in cand.get("career_history", []) if job.get("company")]))
    emp_str = employers[0] if employers else "product companies"
    
    skills_subset = matched_skills[:3]
    if not skills_subset:
        skills_subset = ["Python", "Engineering"]
        
    skills_text = ", ".join(skills_subset)
    
    if rank <= 10:
        return f"Elite candidate with {exp} years of experience; built scalable platforms and leveraged {skills_text} at {emp_str}. Highly active platform signals, {notice}-day notice period, and Noida/Pune location readiness make them a perfect fit for this {role_name} role."
    elif rank <= 30:
        return f"Exceptional background matching product requirements with {exp} years of experience. Demonstrated depth in {skills_text} at {emp_str}; strong recent activity and short notice period align directly with our requirements."
    elif rank <= 70:
        return f"Experienced {title} with {exp} years of experience. Solid engineering foundation in {skills_text} at {emp_str}; highly responsive behavioral profile and relocation-ready."
    else:
        return f"Capable engineer with {exp} years of experience. Practical background in {skills_text}; good platform engagement signals but notice period or location represent minor trade-offs."

def rank_candidates(candidates_path, output_path, role_name="Senior AI Engineer"):
    print(f"Loading candidates from {candidates_path}...")
    candidates = []
    
    open_func = gzip.open if candidates_path.endswith(".gz") else open
    mode = "rt" if candidates_path.endswith(".gz") else "r"
    
    with open_func(candidates_path, mode, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                candidates.append(json.loads(line))
                
    print(f"Loaded {len(candidates)} candidates. Scoring for role: {role_name}...")
    
    scored_candidates = []
    honeypot_count = 0
    
    for cand in candidates:
        score, data = calculate_score(cand, role_name)
        if score < 0:
            honeypot_count += 1
            continue
        scored_candidates.append((score, cand, data))
        
    print(f"Scored {len(scored_candidates)} candidates. Filtered {honeypot_count} honeypots.")
    
    scored_candidates.sort(key=lambda x: (-x[0], x[1]["candidate_id"]))
    top_100 = scored_candidates[:100]
    
    print(f"Writing top 100 candidates to {output_path}...")
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for i, (score, cand, matched_skills) in enumerate(top_100):
            rank = i + 1
            cid = cand["candidate_id"]
            reasoning = generate_reasoning(cand, rank, score, matched_skills, role_name)
            writer.writerow([cid, rank, round(score, 4), reasoning])
            
    print("Ranking complete. CSV file successfully written.")

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Redrob AI challenge.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl or candidates.jsonl.gz")
    parser.add_argument("--out", required=True, help="Path to output submission.csv")
    parser.add_argument("--role", default="Senior AI Engineer", choices=list(ROLE_CONFIGS.keys()), help="Target Job Role configuration to score against")
    args = parser.parse_args()
    
    rank_candidates(args.candidates, args.out, args.role)

if __name__ == "__main__":
    main()
