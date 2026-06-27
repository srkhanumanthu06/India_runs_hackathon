#!/usr/bin/env python3
import json
import argparse
from datetime import datetime
import csv
import sys
import os

# Define Constants
SERVICE_COMPANIES = {
    "infosys", "wipro", "tcs", "capgemini", "hcl", "mindtree", "accenture", 
    "cognizant", "tech mahindra", "mphasis", "cognizant technology solutions"
}

AI_STARTUPS = {
    "glance", "rephrase.ai", "aganitha", "niramai", "saarthi.ai", "sarvam ai", 
    "mad street den", "observe.ai", "krutrim", "wysa", "haptik"
}

PRODUCT_COMPANIES = {
    "swiggy", "zomato", "razorpay", "cred", "flipkart", "meesho", "nykaa", 
    "inmobi", "byju's", "policybazaar", "ola", "zoho", "paytm", "unacademy", 
    "pharmeasy", "upgrad", "freshworks", "phonepe", "dream11", "pied piper", 
    "initech", "hooli", "wayne enterprises", "stark industries", "globex inc", 
    "dunder mifflin", "acme corp"
}

CORE_AI_ML_TITLES = {
    "ml engineer", "ai research engineer", "data scientist", "senior software engineer (ml)", 
    "computer vision engineer", "junior ml engineer", "ai specialist", "recommendation systems engineer", 
    "machine learning engineer", "applied ml engineer", "search engineer", "ai engineer", 
    "senior data scientist", "nlp engineer", "senior nlp engineer", "senior machine learning engineer", 
    "staff machine learning engineer", "senior ai engineer", "senior applied scientist", "lead ai engineer"
}

BACKEND_DATA_TITLES = {
    "software engineer", "backend engineer", "data engineer", "senior software engineer", 
    "senior data engineer", "analytics engineer", "data analyst"
}

GENERAL_SE_TITLES = {
    "full stack developer", "cloud engineer", "java developer", ".net developer", 
    "devops engineer", "mobile developer", "frontend engineer", "qa engineer"
}

UNRELATED_TITLES = {
    "business analyst", "hr manager", "mechanical engineer", "accountant", 
    "project manager", "customer support", "operations manager", "content writer", 
    "sales executive", "civil engineer", "graphic designer", "marketing manager"
}

CORE_ML_SKILLS = {
    "information retrieval", "semantic search", "sentence transformers", "embeddings", 
    "vector search", "rag", "llms", "hugging face transformers", "fine-tuning llms", 
    "recommendation systems", "qlora", "langchain", "prompt engineering", "pinecone", 
    "weaviate", "qdrant", "milvus", "opensearch", "elasticsearch", "faiss"
}

CV_SPEECH_SKILLS = {
    "yolo", "gans", "opencv", "asr", "image classification", "computer vision", 
    "speech recognition", "cnn", "object detection", "diffusion models", "tts"
}

CURRENT_DATE = datetime(2026, 6, 27)

def is_honeypot(cand):
    # Rule 1: Individual career history job duration exceeds its date range by > 3 months
    history = cand.get("career_history", [])
    for job in history:
        start_str = job.get("start_date")
        end_str = job.get("end_date")
        dur = job.get("duration_months", 0)
        
        if start_str:
            try:
                start_date = datetime.strptime(start_str, "%Y-%m-%d")
                if end_str:
                    end_date = datetime.strptime(end_str, "%Y-%m-%d")
                else:
                    end_date = CURRENT_DATE
                
                diff_months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
                if dur > diff_months + 3:
                    return True
            except:
                pass
                
    # Rule 2: Skill has duration_months == 0
    skills = cand.get("skills", [])
    for s in skills:
        if s.get("duration_months", 0) == 0:
            return True
            
    # Rule 3: Profile YOE exceeds sum of job durations by more than 3.0 years
    yoe = cand.get("profile", {}).get("years_of_experience", 0)
    sum_dur_years = sum(job.get("duration_months", 0) for job in history) / 12.0
    if yoe > sum_dur_years + 3.0:
        return True
        
    return False

def has_any_ml_title_in_history(cand):
    history = cand.get("career_history", [])
    for job in history:
        title = job.get("title", "").lower()
        if any(kw in title for kw in ["ml", "machine learning", "ai ", "data scientist", "nlp", "search", "retrieval", "recommendation"]):
            return True
    return False

def calculate_heuristic_score(cand):
    profile = cand.get("profile", {})
    current_title = profile.get("current_title", "").lower()
    
    # Title score
    if any(title in current_title for title in CORE_AI_ML_TITLES):
        title_val = 100
    elif any(title in current_title for title in BACKEND_DATA_TITLES):
        title_val = 70
    elif any(title in current_title for title in GENERAL_SE_TITLES):
        title_val = 30
    else:
        title_val = 0
        
    # Skills score (count matches)
    skills = cand.get("skills", [])
    skills_count = sum(1 for s in skills if s.get("name", "").lower() in CORE_ML_SKILLS)
    
    # YOE score
    yoe = profile.get("years_of_experience", 0)
    if 5.0 <= yoe <= 9.0:
        yoe_val = 50
    elif 9.0 < yoe <= 12.0 or 4.0 <= yoe < 5.0:
        yoe_val = 35
    elif 12.0 < yoe <= 15.0 or 3.0 <= yoe < 4.0:
        yoe_val = 20
    else:
        yoe_val = 0
        
    return title_val + (skills_count * 5) + yoe_val

def score_candidate_stage2(cand):
    profile = cand.get("profile", {})
    history = cand.get("career_history", [])
    skills = cand.get("skills", [])
    signals = cand.get("redrob_signals", {})
    edu = cand.get("education", [])
    
    current_title = profile.get("current_title", "").lower()
    
    # --- Disqualifiers ---
    # 1. IT Services ONLY
    companies = [job.get("company", "").lower() for job in history if job.get("company")]
    if companies:
        only_services = all(comp in SERVICE_COMPANIES for comp in companies)
        if only_services:
            return 0.0
            
    # 2. CV/Speech only (No core ML/NLP/IR)
    has_cv_speech = any(s.get("name", "").lower() in CV_SPEECH_SKILLS for s in skills)
    has_core_ml = any(s.get("name", "").lower() in CORE_ML_SKILLS for s in skills)
    if has_cv_speech and not has_core_ml:
        return 0.0
        
    # 3. Pure Research / Academic ONLY
    job_descriptions = [job.get("description", "").lower() for job in history]
    job_titles = [job.get("title", "").lower() for job in history]
    all_text = " ".join(job_descriptions + job_titles)
    is_academic = all(any(kw in title for kw in ["assistant", "research scholar", "phd", "academic", "university", "teaching"]) for title in job_titles)
    if is_academic and "production" not in all_text and "deployed" not in all_text:
        return 0.0
        
    # 4. Job Hopper
    avg_tenure_months = 0
    if len(history) > 0:
        total_months = sum(job.get("duration_months", 0) for job in history)
        avg_tenure_months = total_months / len(history)
        
    # --- Detailed Scoring Components ---
    # Component 1: Title Score (Max 25)
    title_score = 0
    if any(title in current_title for title in CORE_AI_ML_TITLES):
        title_score = 25
    elif any(title in current_title for title in BACKEND_DATA_TITLES):
        title_score = 20
    elif any(title in current_title for title in GENERAL_SE_TITLES):
        title_score = 10
    else:
        # Check if they had a past ML title
        if has_any_ml_title_in_history(cand):
            title_score = 15
            
    # Component 2: Skills Score (Max 25)
    skills_points = 0
    skills_count = 0
    for s in skills:
        sname_lower = s.get("name", "").lower()
        if sname_lower in CORE_ML_SKILLS:
            skills_count += 1
            prof = s.get("proficiency", "beginner")
            base = 5 if prof == "expert" else 4 if prof == "advanced" else 3 if prof == "intermediate" else 1
            endorsements = s.get("endorsements", 0)
            duration = s.get("duration_months", 0)
            
            end_mult = 1.0 + min(endorsements / 20.0, 0.5)
            dur_mult = 1.0 + min(duration / 36.0, 0.5)
            
            skills_points += base * end_mult * dur_mult
            
    # Normalize skills_points to max of 25 (e.g. 5 strong skills = max score)
    normalized_skills_score = min((skills_points / 25.0) * 25.0, 25.0)
    
    # Component 3: Experience & Company Quality Score (Max 20)
    # YOE Score (max 10)
    yoe = profile.get("years_of_experience", 0)
    if 5.0 <= yoe <= 9.0:
        yoe_points = 10
    elif 9.0 < yoe <= 12.0 or 4.0 <= yoe < 5.0:
        yoe_points = 8
    elif 12.0 < yoe <= 15.0 or 3.0 <= yoe < 4.0:
        yoe_points = 5
    else:
        yoe_points = 1
        
    # Company History Score (max 10)
    comp_points = 0
    seen_companies = set()
    for comp in companies:
        if comp in seen_companies:
            continue
        seen_companies.add(comp)
        if comp in AI_STARTUPS:
            comp_points += 5
        elif comp in PRODUCT_COMPANIES:
            comp_points += 3
    comp_score = min(comp_points, 10)
    exp_quality_score = yoe_points + comp_score
    
    # Component 4: Location & Notice Period Score (Max 10)
    # Location (max 6)
    loc_score = 0
    loc_str = profile.get("location", "").lower()
    country_str = profile.get("country", "").lower()
    
    is_india = "india" in country_str or loc_str in ["pune", "noida", "gurgaon", "delhi", "mumbai", "hyderabad", "bangalore", "chennai"]
    
    if "pune" in loc_str or "noida" in loc_str:
        loc_score = 6
    elif is_india and any(city in loc_str for city in ["gurgaon", "delhi", "ncr", "mumbai", "hyderabad", "bangalore", "chennai"]):
        loc_score = 4
    elif is_india:
        loc_score = 3 if signals.get("willing_to_relocate", False) else 2
    else:
        loc_score = 1
        
    # Notice Period (max 4)
    np_days = signals.get("notice_period_days", 180)
    if np_days <= 30:
        np_score = 4
    elif np_days <= 60:
        np_score = 3
    elif np_days <= 90:
        np_score = 1
    else:
        np_score = 0
        
    logistics_score = loc_score + np_score
    
    # --- Behavioral Signals Modifier ---
    modifier = 1.0
    
    # 1. Recruiter Response Rate
    rrr = signals.get("recruiter_response_rate", 0.0)
    if rrr > 0.8:
        modifier += 0.10
    elif rrr > 0.5:
        modifier += 0.05
    elif rrr < 0.3:
        modifier -= 0.15
    elif rrr < 0.1:
        modifier -= 0.40
        
    # 2. Activity Recency
    lad_str = signals.get("last_active_date")
    if lad_str:
        try:
            lad = datetime.strptime(lad_str, "%Y-%m-%d")
            days_since_active = (CURRENT_DATE - lad).days
            if days_since_active <= 30:
                modifier += 0.10
            elif days_since_active > 180:
                modifier -= 0.50
            elif days_since_active > 90:
                modifier -= 0.20
        except:
            pass
            
    # 3. Open to work flag
    if signals.get("open_to_work_flag", False):
        modifier += 0.05
        
    # 4. GitHub activity score
    gas = signals.get("github_activity_score", -1)
    if gas > 60:
        modifier += 0.10
    elif gas > 30:
        modifier += 0.05
    elif gas == -1:
        modifier -= 0.05
        
    # 5. Interview completion rate
    icr = signals.get("interview_completion_rate", 0.0)
    if icr < 0.5:
        modifier -= 0.15
    elif icr > 0.8:
        modifier += 0.05
        
    # 6. Offer acceptance rate
    oar = signals.get("offer_acceptance_rate", -1)
    if oar != -1 and oar < 0.3:
        modifier -= 0.10
        
    # Apply tenure penalty if job hopper
    if avg_tenure_months > 0 and avg_tenure_months < 15:
        modifier *= 0.70
        
    modifier = max(0.1, min(modifier, 1.3))
    
    # Calculate Final Score
    base_score = title_score + normalized_skills_score + exp_quality_score + logistics_score
    final_score = base_score * modifier
    
    # Map to 0-100 scale based on theoretical max score of 104.0
    final_score_normalized = (final_score / 104.0) * 100.0
    return round(final_score_normalized, 4)

def generate_reasoning(cand):
    profile = cand.get("profile", {})
    signals = cand.get("redrob_signals", {})
    skills = cand.get("skills", [])
    
    title = profile.get("current_title", "AI Engineer")
    yoe = profile.get("years_of_experience", 0)
    
    # Find matching core ML skills
    ml_skills = [s.get("name") for s in skills if s.get("name", "").lower() in CORE_ML_SKILLS]
    if not ml_skills:
        ml_skills = [s.get("name") for s in skills[:2]] # Fallback to top 2 skills if no core ML skills
    
    core_skills_str = ", ".join(ml_skills[:3]) if ml_skills else "AI development"
    
    rrr = signals.get("recruiter_response_rate", 0.0)
    loc = profile.get("location", "India")
    
    # Identify key product company worked at
    history = cand.get("career_history", [])
    prod_comp = None
    for job in history:
        comp = job.get("company", "")
        if comp.lower() in PRODUCT_COMPANIES or comp.lower() in AI_STARTUPS:
            prod_comp = comp
            break
            
    if prod_comp:
        reasoning = f"{title} with {yoe:.1f} yrs experience, including product work at {prod_comp}; expert in {core_skills_str}; {loc}-based with {rrr:.0%} response rate."
    else:
        reasoning = f"{title} with {yoe:.1f} yrs experience; has core ML skills in {core_skills_str}; {loc}-based with {rrr:.0%} response rate."
        
    return reasoning

def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer JD.")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to write the submission CSV")
    args = parser.parse_args()
    
    if not os.path.exists(args.candidates):
        print(f"Error: Candidate file not found at {args.candidates}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Starting ranking process. Reading from: {args.candidates}")
    
    # Stage 1: Retrieval & Filtering
    print("Stage 1: Running fast filter and heuristic scoring...")
    candidate_pool = []
    
    with open(args.candidates, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            
            # Check 1: Exclude Honeypots
            if is_honeypot(cand):
                continue
                
            # Check 2: Exclude unrelated current titles that have NO ML history
            # (Stage 1 role filter)
            profile = cand.get("profile", {})
            current_title = profile.get("current_title", "").lower()
            if any(ut in current_title for ut in UNRELATED_TITLES):
                # If current title is unrelated, they are only eligible if they have a past ML job title.
                # Otherwise, they are keyword-stuffer traps.
                if not has_any_ml_title_in_history(cand):
                    continue
                    
            # Calculate heuristic score for filtering
            h_score = calculate_heuristic_score(cand)
            candidate_pool.append((h_score, cand))
            
    print(f"Stage 1 complete. Filtered pool size: {len(candidate_pool)}")
    
    # Sort by heuristic score and pick top 2,000 for Stage 2
    candidate_pool.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidate_pool[:2000]
    
    # Stage 2: Detailed Scoring and Re-ranking
    print("Stage 2: Running detailed scoring and re-ranking...")
    scored_candidates = []
    for _, cand in top_candidates:
        score = score_candidate_stage2(cand)
        if score > 0.0:  # Candidates scoring 0 are disqualified
            scored_candidates.append((score, cand))
            
    print(f"Stage 2 complete. Scored pool size: {len(scored_candidates)}")
    
    # Sort by Score (Descending), break ties by candidate_id (Ascending)
    scored_candidates.sort(key=lambda x: (-x[0], x[1]["candidate_id"]))
    
    # Take top 100
    final_top_100 = scored_candidates[:100]
    
    if len(final_top_100) < 100:
        print(f"Warning: Only found {len(final_top_100)} qualifying candidates. Using filler.", file=sys.stderr)
        
    print(f"Writing top 100 candidates to: {args.out}")
    
    # Write to CSV
    with open(args.out, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        
        for rank_idx, (score, cand) in enumerate(final_top_100, 1):
            cid = cand["candidate_id"]
            reasoning = generate_reasoning(cand)
            writer.writerow([cid, rank_idx, f"{score:.4f}", reasoning])
            
    print("Ranking successfully completed.")

if __name__ == "__main__":
    main()
