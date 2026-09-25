import re

SKILLS_DB = [
    "java", "core java", "python", "c", "c++", "javascript", "typescript", "react", "html", "css",
    "node.js", "express.js", "spring", "spring boot", "rest api", "mysql", "sql", "mongodb",
    "git", "github", "docker", "aws", "azure", "machine learning", "artificial intelligence",
    "data science", "testing", "manual testing", "automation testing", "test cases", "selenium",
    "jira", "defect tracking", "sit", "uat", "rtm", "oop", "dsa", "cloud computing", "microservices"
]

SKILL_ALIASES = {
    "core java": "java",
    "spring boot": "spring boot", # Ensure Spring Boot doesn't merge with Spring unless required
    "mysql": "mysql", 
    "sql": "sql",
    "test cases": "test cases",
    "sit": "sit",
    "uat": "uat",
    "sit/uat": "sit/uat",
    "rtm": "rtm",
    "defect tracking": "defect tracking"
}

DEGREES = ["b.tech", "b.e", "m.tech", "mca", "bca", "b.sc", "m.sc", "diploma", "bachelor", "master", "phd", "degree", "graduation"]

def prevent_auto_link(text: str) -> str:
    """Inserts a zero-width space after a dot to prevent Telegram from auto-linking strings like B.Tech"""
    return re.sub(r'(?i)\.(tech|js|io|com|net|org|ai|dev)', lambda m: f".\u200B{m.group(1)}", text)

def normalize_skill(skill: str) -> str:
    return SKILL_ALIASES.get(skill.lower(), skill.lower())

def extract_skills_with_context(text: str) -> set:
    text_lower = text.lower()
    found_skills = set()
    for skill in SKILLS_DB:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.add(skill)
    return found_skills

def split_jd_skills(jd_text: str):
    jd_lower = jd_text.lower()
    
    required_text = jd_lower
    preferred_text = ""
    
    pref_idx = -1
    for keyword in ["preferred", "nice to have", "bonus", "good to have", "advantage", "desirable", "additional"]:
        idx = jd_lower.find(keyword)
        if idx != -1:
            if pref_idx == -1 or idx < pref_idx:
                pref_idx = idx
                
    if pref_idx != -1:
        required_text = jd_lower[:pref_idx]
        preferred_text = jd_lower[pref_idx:]
        
    req_skills = extract_skills_with_context(required_text)
    pref_skills = extract_skills_with_context(preferred_text)
    
    # Remove preferred skills that are already required
    pref_skills = pref_skills - req_skills
    
    return req_skills, pref_skills

def extract_candidate_name(resume_text: str, filename: str) -> str:
    lines = [line.strip() for line in resume_text.split('\n') if line.strip()]
    invalid_names = {"resume", "curriculum vitae", "cv", "work experience", "skills", "education", "summary", "profile", "projects"}
    
    for line in lines[:10]:
        if 2 <= len(line) <= 40 and not any(bad in line.lower() for bad in invalid_names):
            if re.match(r'^[A-Za-z\s\.]+$', line):
                return line.title()
                
    name = filename.replace(".pdf", "").replace(".docx", "").replace(".txt", "").replace("-", " ").replace("_", " ")
    if "resume" in name.lower():
        name = name.lower().replace("resume", "").strip().title()
    if not name:
        name = "Not detected"
    return name

def extract_target_role(jd_text: str) -> str:
    lines = [line.strip() for line in jd_text.split('\n') if line.strip()]
    for line in lines[:15]:
        lower_line = line.lower()
        if "role:" in lower_line or "title:" in lower_line or "position:" in lower_line or "role title" in lower_line:
            parts = re.split(r':|-', line, 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip().title()
                
    for line in lines[:5]:
        if 5 <= len(line) <= 50 and not line.lower().startswith("job description"):
            return line.title()
            
    return "Not specified"

def analyze_resume_local(jd_text: str, resume_text: str) -> dict:
    jd_lower = jd_text.lower()
    resume_lower = resume_text.lower()
    
    cand_name = extract_candidate_name(resume_text, "Candidate")
    target_role = prevent_auto_link(extract_target_role(jd_text))
    
    req_jd_raw, pref_jd_raw = split_jd_skills(jd_text)
    resume_skills_raw = extract_skills_with_context(resume_text)
    
    req_jd_norm = {normalize_skill(s) for s in req_jd_raw}
    pref_jd_norm = {normalize_skill(s) for s in pref_jd_raw}
    resume_skills_norm = {normalize_skill(s) for s in resume_skills_raw}
    
    matched_req = [s for s in req_jd_raw if normalize_skill(s) in resume_skills_norm]
    missing_req = [s for s in req_jd_raw if normalize_skill(s) not in resume_skills_norm]
    
    matched_pref = [s for s in pref_jd_raw if normalize_skill(s) in resume_skills_norm]
    missing_pref = [s for s in pref_jd_raw if normalize_skill(s) not in resume_skills_norm]
    
    all_missing = missing_req + missing_pref
    
    if not req_jd_raw:
        skill_coverage = 100
        skills_match_percent = 100
    else:
        skill_coverage = int((len(matched_req) / len(req_jd_raw)) * 100)
        skills_match_percent = skill_coverage
        
    # Keyword overlap
    jd_words = set(re.findall(r'\b\w{4,}\b', jd_lower))
    resume_words = set(re.findall(r'\b\w{4,}\b', resume_lower))
    overlap = len(jd_words.intersection(resume_words))
    keyword_score = min(int((overlap / max(1, len(jd_words))) * 100 * 1.5), 100)
    jd_relevance_percent = keyword_score
    
    # Experience Analysis
    has_jd_fresher = any(w in jd_lower for w in ["fresher", "entry level", "0 year", "0-2 year"])
    
    # Check if resume has ANY experience (projects count for freshers)
    has_exp = "experience" in resume_lower or "project" in resume_lower or "internship" in resume_lower
    # Check if resume has PROFESSIONAL experience
    has_prof_exp = "work experience" in resume_lower or "employment" in resume_lower or "professional experience" in resume_lower

    if has_jd_fresher:
        if has_prof_exp or has_exp:
            exp_align_percent = 100
            exp_desc = "The position is intended for freshers. The candidate's academic projects and internship exposure provide relevant supporting experience for the role."
        else:
            exp_align_percent = 80
            exp_desc = "The position is intended for freshers, so the candidate meets the baseline experience requirement."
    else:
        # JD expects experience
        jd_years_match = re.search(r'(\d+)\+?\s*years', jd_lower)
        if jd_years_match and has_prof_exp:
            exp_align_percent = 90
            exp_desc = f"The candidate demonstrates professional work experience, aligning with the requested {jd_years_match.group(1)}+ years."
        elif has_prof_exp:
            exp_align_percent = 90
            exp_desc = "The candidate demonstrates clear professional work experience aligning with the JD."
        elif has_exp:
            exp_align_percent = 50
            exp_desc = "The candidate appears to be a fresher with relevant academic or project experience. The JD emphasizes professional experience, which is not strongly demonstrated."
        else:
            exp_align_percent = 20
            exp_desc = "Direct project or professional experience is not explicitly detected in the resume."
            
    exp_align_percent = max(0, min(100, exp_align_percent))
    
    # Education Analysis
    found_deg = [deg for deg in DEGREES if deg in resume_lower]
    has_jd_edu = any(deg in jd_lower for deg in DEGREES)
    
    if found_deg:
        edu_align_percent = 100
        deg_display = prevent_auto_link(found_deg[0].upper()) if found_deg[0] != "degree" else "a relevant degree"
        edu_desc = f"The candidate has {deg_display} qualifications, which aligns with the educational expectations."
    else:
        edu_align_percent = 40
        edu_desc = "Specific expected educational degrees were not explicitly verified in the resume."
        if not has_jd_edu:
            edu_align_percent = 100
            edu_desc = "No strict education requirements were found in the JD, so current qualifications are presumed acceptable."

    edu_align_percent = max(0, min(100, edu_align_percent))

    # Resume sections
    section_keywords = ["skills", "education", "experience", "projects", "summary", "profile", "certifications", "objective"]
    found_sections = sum(1 for sec in section_keywords if sec in resume_lower)
    sections_score = min(100, int((found_sections / 4) * 100))

    # Terminology/relevance
    tech_terms = ["agile", "scrum", "sdlc", "lifecycle", "architecture", "design", "development", "testing", "deployment", "ci/cd", "pipeline", "framework", "api", "database", "infrastructure", "engineer", "developer"]
    found_terms = sum(1 for term in tech_terms if term in resume_lower)
    terminology_score = min(100, int((found_terms / 3) * 100))

    # Calculate deterministic compatibility breakdown
    comp_score = (skills_match_percent * 0.50) + (exp_align_percent * 0.20) + (edu_align_percent * 0.15) + (jd_relevance_percent * 0.15)
    comp_score = int(min(comp_score, 100))
    rating = round(comp_score / 10.0, 1)
    
    # ATS Deterministic Score
    ats_score = int((skill_coverage * 0.40) + (keyword_score * 0.20) + (edu_align_percent * 0.15) + (exp_align_percent * 0.10) + (sections_score * 0.10) + (terminology_score * 0.05))
    ats_score = min(ats_score, 100)
    
    # Strengths
    strengths = []
    if matched_req:
        strengths.append(prevent_auto_link(f"Solid foundation in {', '.join([s.title() for s in matched_req[:3]])}"))
    if has_prof_exp:
        strengths.append("Possesses professional work experience")
    elif has_exp:
        strengths.append("Relevant academic projects and internship background")
    if found_deg:
        strengths.append(prevent_auto_link(f"Meets academic qualifications ({found_deg[0].upper()})"))
        
    if not strengths:
        strengths.append("General software development interest")

    # Improvements
    suggestions = []
    for ms in missing_req[:3]:
        if ms in ["manual testing", "test cases", "sit", "uat", "rtm", "defect tracking", "selenium", "testing"]:
            suggestions.append(f"Build foundational {prevent_auto_link(ms.title())} knowledge and execution skills.")
        elif ms in ["java", "core java"]:
            suggestions.append("Strengthen Core Java and OOP fundamentals.")
        else:
            suggestions.append(f"Acquire practical project experience in {prevent_auto_link(ms.title())}.")
            
    if not suggestions and missing_pref:
        suggestions.append(f"Consider learning preferred skills like {prevent_auto_link(missing_pref[0].title())} to stand out.")
    elif not suggestions:
        suggestions.append("Continue building complex, real-world applications.")
        
    # Recruitment Summary
    summary = f"The candidate has a foundation in {prevent_auto_link(', '.join(matched_req[:2]).title()) if matched_req else 'general technology'}, supported by their technical background. "
    
    if has_jd_fresher:
        summary += "The position is designed for freshers, so the candidate's experience level accurately aligns with the stated requirement. "
    else:
        if has_prof_exp:
            summary += "The candidate possesses professional experience that aligns with the role. "
        else:
            summary += "Professional experience is a development area compared to JD expectations. "
            
    if missing_req:
        summary += f"The main gaps are in {prevent_auto_link(', '.join(missing_req[:3]).title())}. Strengthening these specific areas would significantly improve overall alignment with the role."
    else:
        summary += "Overall alignment is exceptionally strong with no major required skill gaps detected."

    return {
        "candidate_name": cand_name,
        "job_role": target_role,
        "compatibility_score": comp_score,
        "ats_score": ats_score,
        "rating": rating,
        
        "breakdown_skills": skills_match_percent,
        "breakdown_exp": exp_align_percent,
        "breakdown_edu": edu_align_percent,
        "breakdown_rel": jd_relevance_percent,
        "breakdown_sections": sections_score,
        "breakdown_terminology": terminology_score,
        
        "matched_skills": [prevent_auto_link(s) for s in set(matched_req)],
        "missing_skills": [prevent_auto_link(s) for s in set(missing_req)],
        "matched_pref_skills": [prevent_auto_link(s) for s in set(matched_pref)],
        "missing_pref_skills": [prevent_auto_link(s) for s in set(missing_pref)],
        "skill_coverage": skill_coverage,
        
        "experience_alignment": exp_desc,
        "education_alignment": edu_desc,
        "strengths": strengths[:4],
        "improvement_suggestions": suggestions[:4],
        "recruitment_summary": summary,
        "all_missing": list(set(all_missing)) # For course recommender
    }
