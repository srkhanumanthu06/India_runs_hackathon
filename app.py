import streamlit as st
import json
import pandas as pd
from datetime import datetime
import io
import csv
import sys

# Import our ranking functions from rank.py
from rank import is_honeypot, calculate_heuristic_score, score_candidate_stage2, generate_reasoning, UNRELATED_TITLES, has_any_ml_title_in_history

st.set_page_config(page_title="Redrob Candidate Ranker", layout="wide")

st.title("🎯 Redrob AI Candidate Discovery & Ranking Sandbox")
st.markdown("Upload a candidate pool in JSONL format to see the top ranks.")

uploaded_file = st.file_uploader("Upload candidates.jsonl", type=["jsonl", "json"])

if uploaded_file is not None:
    # Read candidates
    st.info("Reading candidate pool...")
    candidates = []
    
    bytes_data = uploaded_file.getvalue()
    
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
    
    # Run Stage 1 (Fast Filtering)
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
    
    # Run Stage 2 (Detailed Re-ranking)
    scored_candidates = []
    for _, cand in top_candidates:
        score = score_candidate_stage2(cand)
        if score > 0.0:
            scored_candidates.append((score, cand))
            
    scored_candidates.sort(key=lambda x: (-x[0], x[1]["candidate_id"]))
    final_top = scored_candidates[:100]
    
    if len(final_top) == 0:
        st.warning("No candidates matched the criteria.")
    else:
        # Prepare display data
        rows = []
        for rank_idx, (score, cand) in enumerate(final_top, 1):
            rows.append({
                "Rank": rank_idx,
                "Candidate ID": cand["candidate_id"],
                "Name": cand["profile"]["anonymized_name"],
                "Score": f"{score:.4f}",
                "Current Title": cand["profile"]["current_title"],
                "YOE": cand["profile"]["years_of_experience"],
                "Location": cand["profile"]["location"],
                "Reasoning": generate_reasoning(cand)
            })
            
        df = pd.DataFrame(rows)
        st.subheader(f"Top Ranked Candidates (Showing {len(final_top)} results)")
        st.dataframe(df, use_container_width=True)
        
        # Prepare CSV for download
        csv_data = io.StringIO()
        csv_writer = csv.writer(csv_data)
        csv_writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for r in rows:
            csv_writer.writerow([r["Candidate ID"], r["Rank"], r["Score"], r["Reasoning"]])
            
        st.download_button(
            label="Download Ranked CSV",
            data=csv_data.getvalue(),
            file_name="submission.csv",
            mime="text/csv"
        )
