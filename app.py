import streamlit as st
import json
import pandas as pd
from datetime import datetime
import io
import csv
import sys
import re

# Import our ranking functions from rank.py
from rank import (
    is_honeypot, calculate_heuristic_score, score_candidate_stage2, 
    generate_reasoning, UNRELATED_TITLES, has_any_ml_title_in_history, 
    CORE_ML_SKILLS, SERVICE_COMPANIES, PRODUCT_COMPANIES, AI_STARTUPS
)

st.set_page_config(page_title="Aven AI Candidate Discovery", layout="wide")

st.title("🎯 Aven AI Candidate Discovery & Ranking Sandbox")
st.markdown("An intelligent, 2-stage recruiter matching system with built-in explainability, side-by-side comparison, and screening chatbot.")

# File uploader
uploaded_file = st.file_uploader("Upload candidates.jsonl or candidates.jsonl.gz", type=["jsonl", "json", "gz"])

# Helper function to generate candidate comparison verdict
def generate_comparison_verdict(cand_a, score_a, rank_a, cand_b, score_b, rank_b):
    name_a = cand_a["profile"]["anonymized_name"]
    name_b = cand_b["profile"]["anonymized_name"]
    yoe_a = cand_a["profile"]["years_of_experience"]
    yoe_b = cand_b["profile"]["years_of_experience"]
    
    reasons = []
    # YOE Comparison
    if abs(yoe_a - yoe_b) >= 0.5:
        better = name_a if yoe_a > yoe_b else name_b
        worse = name_b if yoe_a > yoe_b else name_a
        diff = abs(yoe_a - yoe_b)
        reasons.append(f"**Experience Depth**: {better} has more years of experience ({max(yoe_a, yoe_b):.1f} yrs) compared to {worse} ({min(yoe_a, yoe_b):.1f} yrs)")
        
    # Skills Comparison
    skills_a = [s.get("name", "") for s in cand_a.get("skills", []) if s.get("name", "").lower() in CORE_ML_SKILLS]
    skills_b = [s.get("name", "") for s in cand_b.get("skills", []) if s.get("name", "").lower() in CORE_ML_SKILLS]
    if len(skills_a) != len(skills_b):
        better = name_a if len(skills_a) > len(skills_b) else name_b
        worse = name_b if len(skills_a) > len(skills_b) else name_a
        reasons.append(f"**Core AI/ML Skills**: {better} lists more core matching skills ({len(skills_a)}: {', '.join(skills_a[:3])}) than {worse} ({len(skills_b)}: {', '.join(skills_b[:3])})")
        
    # Recruiter Response Rate
    rrr_a = cand_a.get("redrob_signals", {}).get("recruiter_response_rate", 0.0)
    rrr_b = cand_b.get("redrob_signals", {}).get("recruiter_response_rate", 0.0)
    if abs(rrr_a - rrr_b) >= 0.05:
        better = name_a if rrr_a > rrr_b else name_b
        worse = name_b if rrr_a > rrr_b else name_a
        reasons.append(f"**Availability / Response Rate**: {better} responds to {max(rrr_a, rrr_b):.0%} of recruiter messages, whereas {worse} responds to only {min(rrr_a, rrr_b):.0%}")
        
    # Location
    loc_a = cand_a.get("profile", {}).get("location", "").lower()
    loc_b = cand_b.get("profile", {}).get("location", "").lower()
    is_a_local = "noida" in loc_a or "pune" in loc_a
    is_b_local = "noida" in loc_b or "pune" in loc_b
    if is_a_local != is_b_local:
        better = name_a if is_a_local else name_b
        worse = name_b if is_a_local else name_a
        reasons.append(f"**Location Proximity**: {better} is located in an office-cadence city (Noida/Pune), while {worse} is in {cand_b['profile']['location'] if is_a_local else cand_a['profile']['location']}")
        
    # Notice Period
    np_a = cand_a.get("redrob_signals", {}).get("notice_period_days", 180)
    np_b = cand_b.get("redrob_signals", {}).get("notice_period_days", 180)
    if abs(np_a - np_b) >= 15:
        better = name_a if np_a < np_b else name_b
        worse = name_b if np_a < np_b else name_a
        reasons.append(f"**Notice Period / Startup Fit**: {better} has a shorter notice period ({min(np_a, np_b)} days) and can join faster than {worse} ({max(np_a, np_b)} days)")
        
    # Verdict output
    verdict = ""
    if rank_a < rank_b:
        verdict += f"### 🏆 Why **{name_a}** (Rank #{rank_a}) ranks higher than **{name_b}** (Rank #{rank_b}):\n"
    else:
        verdict += f"### 🏆 Why **{name_b}** (Rank #{rank_b}) ranks higher than **{name_a}** (Rank #{rank_a}):\n"
        
    if reasons:
        for r in reasons:
            verdict += f"- {r}\n"
    else:
        verdict += "- Minor scoring margins on specific skill endorsements, tenure durations, or login activity recency."
        
    return verdict

# Main logic when file is uploaded
if uploaded_file is not None:
    # Read candidates
    bytes_data = uploaded_file.getvalue()
    candidates = []
    
    # Handle gzipped files (.gz) or raw text files
    if bytes_data.startswith(b'\x1f\x8b'):
        import gzip
        try:
            text_data = gzip.decompress(bytes_data).decode("utf-8", errors="replace")
        except Exception as e:
            st.error(f"Failed to decompress gzip file: {e}")
            st.stop()
    else:
        text_data = bytes_data.decode("utf-8", errors="replace")
            
    stringio = io.StringIO(text_data)
    for line in stringio:
        if not line.strip():
            continue
        try:
            candidates.append(json.loads(line))
        except Exception as e:
            st.error(f"Failed to parse line: {e}")
            
    st.success(f"Successfully loaded {len(candidates)} candidates.")
    
    # 2-Stage Pipeline Processing
    # Stage 1: Retrieval & Filtering
    filtered_pool = []
    for cand in candidates:
        if is_honeypot(cand):
            continue
            
        profile = cand.get("profile", {})
        current_title = profile.get("current_title", "").lower()
        if any(ut in current_title for ut in UNRELATED_TITLES):
            if not has_any_ml_title_in_history(cand):
                continue
                
        h_score = calculate_heuristic_score(cand)
        filtered_pool.append((h_score, cand))
        
    filtered_pool.sort(key=lambda x: x[0], reverse=True)
    top_candidates = filtered_pool[:2000]
    
    # Stage 2: Detailed Re-ranking
    scored_candidates = []
    for _, cand in top_candidates:
        score = score_candidate_stage2(cand)
        if score > 0.0:
            scored_candidates.append((score, cand))
            
    # Sort by score desc, candidate_id asc
    scored_candidates.sort(key=lambda x: (-x[0], x[1]["candidate_id"]))
    final_top_100 = scored_candidates[:100]
    
    # Create database dict for chatbot lookup
    cand_db = {c[1]["candidate_id"]: c for c in scored_candidates}
    # Also lookup by anonymized name (lowercase)
    name_db = {c[1]["profile"]["anonymized_name"].lower(): c for c in scored_candidates}

    # Streamlit Navigation Tabs
    tab1, tab2, tab3 = st.tabs(["📋 Top Candidates", "⚖️ Candidate Comparison", "💬 AI Recruiter Assistant"])
    
    # -------------------------------------------------------------
    # TAB 1: TOP CANDIDATES VIEW & EXPORT
    # -------------------------------------------------------------
    with tab1:
        if len(final_top_100) == 0:
            st.warning("No candidates matched the criteria.")
        else:
            # Prepare display data
            rows = []
            for rank_idx, (score, cand) in enumerate(final_top_100, 1):
                rows.append({
                    "Rank": rank_idx,
                    "Candidate ID": cand["candidate_id"],
                    "Name": cand["profile"]["anonymized_name"],
                    "Score": f"{score * 100:.1f}/100" if score <= 1.0 else f"{score:.1f}/100",
                    "Current Title": cand["profile"]["current_title"],
                    "YOE": cand["profile"]["years_of_experience"],
                    "Location": cand["profile"]["location"],
                    "Reasoning": generate_reasoning(cand)
                })
                
            df = pd.DataFrame(rows)
            st.subheader(f"Top 100 Ranked Candidates")
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Prepare CSV for download
            csv_data = io.StringIO()
            csv_writer = csv.writer(csv_data)
            csv_writer.writerow(["candidate_id", "rank", "score", "reasoning"])
            for r in rows:
                score_val = r["Score"].replace("/100", "")
                csv_writer.writerow([r["Candidate ID"], r["Rank"], score_val, r["Reasoning"]])
                
            st.download_button(
                label="📥 Download Ranked CSV",
                data=csv_data.getvalue(),
                file_name="team_aven.csv",
                mime="text/csv"
            )
            
    # -------------------------------------------------------------
    # TAB 2: SIDE-BY-SIDE CANDIDATE COMPARISON
    # -------------------------------------------------------------
    with tab2:
        st.subheader("⚖️ Compare Candidates Side-by-Side")
        st.write("Select two candidates to compare their credentials and generate an objective verdict.")
        
        # Populate candidate selectbox lists
        candidate_options = [
            f"{c[1]['candidate_id']} - {c[1]['profile']['anonymized_name']} ({c[1]['profile']['current_title']})" 
            for c in final_top_100
        ]
        
        col1, col2 = st.columns(2)
        with col1:
            option_a = st.selectbox("Select Candidate A", candidate_options, index=0)
        with col2:
            option_b = st.selectbox("Select Candidate B", candidate_options, index=min(1, len(candidate_options)-1))
            
        if option_a and option_b:
            id_a = option_a.split(" - ")[0]
            id_b = option_b.split(" - ")[0]
            
            score_a, cand_a = cand_db[id_a]
            score_b, cand_b = cand_db[id_b]
            
            # Find ranks
            rank_a = [i for i, c in enumerate(final_top_100, 1) if c[1]["candidate_id"] == id_a][0]
            rank_b = [i for i, c in enumerate(final_top_100, 1) if c[1]["candidate_id"] == id_b][0]
            
            # Display side-by-side comparison table
            comparison_rows = [
                {"Factor": "Rank", "Candidate A": f"#{rank_a}", "Candidate B": f"#{rank_b}"},
                {"Factor": "Match Score", "Candidate A": f"{score_a*100:.1f}/100" if score_a <= 1.0 else f"{score_a:.1f}/100", "Candidate B": f"{score_b*100:.1f}/100" if score_b <= 1.0 else f"{score_b:.1f}/100"},
                {"Factor": "Name", "Candidate A": cand_a["profile"]["anonymized_name"], "Candidate B": cand_b["profile"]["anonymized_name"]},
                {"Factor": "Current Title", "Candidate A": cand_a["profile"]["current_title"], "Candidate B": cand_b["profile"]["current_title"]},
                {"Factor": "Years of Experience", "Candidate A": f"{cand_a['profile']['years_of_experience']:.1f} years", "Candidate B": f"{cand_b['profile']['years_of_experience']:.1f} years"},
                {"Factor": "Location", "Candidate A": cand_a["profile"]["location"], "Candidate B": cand_b["profile"]["location"]},
                {"Factor": "Notice Period", "Candidate A": f"{cand_a['redrob_signals']['notice_period_days']} days", "Candidate B": f"{cand_b['redrob_signals']['notice_period_days']} days"},
                {"Factor": "Recruiter Response Rate", "Candidate A": f"{cand_a['redrob_signals']['recruiter_response_rate']:.0%}", "Candidate B": f"{cand_b['redrob_signals']['recruiter_response_rate']:.0%}"},
                {"Factor": "Core Skills Match", "Candidate A": ", ".join([s.get("name", "") for s in cand_a.get("skills", []) if s.get("name", "").lower() in CORE_ML_SKILLS][:4]), "Candidate B": ", ".join([s.get("name", "") for s in cand_b.get("skills", []) if s.get("name", "").lower() in CORE_ML_SKILLS][:4])},
            ]
            
            comparison_df = pd.DataFrame(comparison_rows)
            st.table(comparison_df.set_index("Factor"))
            
            # Print Verdict
            st.markdown("---")
            verdict_markdown = generate_comparison_verdict(cand_a, score_a, rank_a, cand_b, score_b, rank_b)
            st.markdown(verdict_markdown)

    # -------------------------------------------------------------
    # TAB 3: CONVERSATIONAL RECRUITER ASSISTANT
    # -------------------------------------------------------------
    with tab3:
        st.subheader("💬 AI Recruiter Assistant")
        st.write("Ask questions about the candidate pool or screening decisions. Since we run offline under strict resource limits, queries are handled by a high-speed, local rule-based screening engine.")
        
        # Initialize chat history
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! I am your candidate screening assistant. Ask me questions like:\n- *Why is CAND_0000031 ranked #14?*\n- *Does Ira Vora have experience with FAISS or Embeddings?*\n- *What is the notice period for CAND_0002025?*\n- *Are they willing to relocate?*"}
            ]
            
        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
        # Handle User Input
        if prompt := st.chat_input("Enter your screening question..."):
            with st.chat_message("user"):
                st.markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Chat logic parsing
            prompt_lower = prompt.lower()
            response = ""
            
            # Extract candidate ID or Name
            cid_match = re.search(r"cand_[0-9]{7}", prompt_lower)
            target_cand_tuple = None
            
            if cid_match:
                cid = cid_match.group(0).upper()
                if cid in cand_db:
                    target_cand_tuple = cand_db[cid]
            else:
                # Try name lookup
                for name, cand_tuple in name_db.items():
                    if name in prompt_lower:
                        target_cand_tuple = cand_tuple
                        break
                        
            if target_cand_tuple:
                score, cand = target_cand_tuple
                name = cand["profile"]["anonymized_name"]
                cid = cand["candidate_id"]
                title = cand["profile"]["current_title"]
                yoe = cand["profile"]["years_of_experience"]
                loc = cand["profile"]["location"]
                
                # Check for specific queries
                # Q1: Why is candidate ranked X?
                if any(kw in prompt_lower for kw in ["why", "reason", "rank", "explain"]):
                    rank_idx = [i for i, c in enumerate(scored_candidates) if c[1]["candidate_id"] == cid]
                    rank_str = f"#{rank_idx[0]+1}" if rank_idx else "N/A"
                    score_str = f"{score*100:.1f}/100" if score <= 1.0 else f"{score:.1f}/100"
                    
                    skills_list = [s.get("name", "") for s in cand.get("skills", []) if s.get("name", "").lower() in CORE_ML_SKILLS]
                    
                    response = (
                        f"**Decision Summary for {name} ({cid})**:\n"
                        f"- **Current Rank**: {rank_str} (Score: {score_str})\n"
                        f"- **Core Fit**: Matches the JD with **{yoe:.1f} years of experience** as a **{title}**.\n"
                        f"- **Skills Match**: Lists **{len(skills_list)} core JD skills** ({', '.join(skills_list[:4])}).\n"
                        f"- **Notice Period**: {cand['redrob_signals']['notice_period_days']} days.\n"
                        f"- **Engagement Multiplier**: Boosted by an active recruiter response rate of **{cand['redrob_signals']['recruiter_response_rate']:.0%}** and a Github activity score of **{cand['redrob_signals']['github_activity_score']}**."
                    )
                    
                # Q2: Relocation
                elif "relocate" in prompt_lower:
                    reloc = cand["redrob_signals"]["willing_to_relocate"]
                    status = "Willing to relocate" if reloc else "Not willing to relocate"
                    response = f"📦 **Relocation status for {name}**: {status} (Current location: {loc})."
                    
                # Q3: Notice Period
                elif any(kw in prompt_lower for kw in ["notice", "join", "start"]):
                    np_days = cand["redrob_signals"]["notice_period_days"]
                    response = f"📅 **Notice period for {name}**: {np_days} days."
                    
                # Q4: Skill checks
                elif any(sname in prompt_lower for sname in ["faiss", "pinecone", "weaviate", "milvus", "rag", "llm", "embeddings", "python", "spark", "airflow"]):
                    # Find which skill they asked about
                    queried_skill = None
                    for sname in ["faiss", "pinecone", "weaviate", "milvus", "rag", "llm", "embeddings", "python", "spark", "airflow"]:
                        if sname in prompt_lower:
                            queried_skill = sname
                            break
                            
                    cand_skills = {s.get("name", "").lower(): s for s in cand.get("skills", [])}
                    matched_skill = None
                    for name_key, s_obj in cand_skills.items():
                        if queried_skill in name_key:
                            matched_skill = s_obj
                            break
                            
                    if matched_skill:
                        response = f"✅ Yes, **{name}** lists **{matched_skill['name']}** on their profile with **{matched_skill['proficiency']}** proficiency and **{matched_skill['duration_months']} months** of usage."
                    else:
                        response = f"❌ No, **{name}** does not list experience with **{queried_skill.upper()}** on their profile."
                        
                # General Profile Summary
                else:
                    summary = cand["profile"]["summary"]
                    response = (
                        f"📝 **Profile details for {name} ({cid})**:\n"
                        f"- **Title**: {title}\n"
                        f"- **Experience**: {yoe:.1f} years\n"
                        f"- **Location**: {loc}\n"
                        f"- **Summary**: *{summary}*"
                    )
            else:
                # If no candidate found in prompt
                response = "I couldn't locate a candidate matching that name or ID (e.g. `CAND_0000031`) in your query. Please specify a valid candidate ID or candidate name so I can search their profile facts."
                
            # Display response
            with st.chat_message("assistant"):
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
