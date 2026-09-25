# scorer.py
import re

def calculate_ats_score(job_description: str, resume_text: str) -> dict:
    jd_lower = job_description.lower()
    resume_lower = resume_text.lower()
    
    # 1. Keyword/Skill Coverage — 40 points
    # Extract words > 4 chars from JD to approximate keywords
    jd_words = set(re.findall(r'\b[a-z]{4,}\b', jd_lower))
    if not jd_words:
        keyword_score = 0
    else:
        matched_words = [w for w in jd_words if w in resume_lower]
        keyword_ratio = len(matched_words) / len(jd_words)
        # Cap at 40. We multiply by 1.5 because matching 100% of all JD words is highly unlikely
        keyword_score = min(40, int(keyword_ratio * 40 * 1.5))

    # 2. Resume Text Completeness — 20 points
    # Check for basic sections
    completeness_score = 0
    sections = {
        "contact": r'\b(email|phone|@|[0-9]{3}-[0-9]{3}-[0-9]{4})\b',
        "skills": r'\b(skills|technologies|tools)\b',
        "education": r'\b(education|university|college|degree|bachelor|master)\b',
        "experience": r'\b(experience|employment|work history|career)\b',
        "projects": r'\b(projects|portfolio)\b'
    }
    
    for key, pattern in sections.items():
        if re.search(pattern, resume_lower):
            completeness_score += 4 # 5 sections * 4 points = 20 points maximum

    # 3. ATS-Friendly Structure — 20 points
    # Evaluates readability from extracted text
    structure_score = 0
    word_count = len(resume_text.split())
    if word_count > 150:
        structure_score += 10
    elif word_count > 50:
        structure_score += 5
        
    # Check if standard alphanumeric characters make up > 70% of the text.
    # If not, it might be a corrupted PDF extraction.
    alpha_num_count = len(re.findall(r'[a-zA-Z0-9]', resume_text))
    if len(resume_text) > 0 and (alpha_num_count / len(resume_text)) > 0.7:
        structure_score += 10

    # 4. Job Title/Role Alignment — 10 points
    roles = ['engineer', 'developer', 'manager', 'analyst', 'scientist', 'consultant', 'architect', 'designer', 'administrator']
    jd_roles = [r for r in roles if r in jd_lower]
    
    role_alignment_score = 0
    if not jd_roles:
        role_alignment_score = 10 # Free points if JD doesn't list standard roles
    else:
        for r in jd_roles:
            if r in resume_lower:
                role_alignment_score = 10
                break

    # 5. Achievement/Project Evidence — 10 points
    evidence_score = 0
    # Look for measurable numbers or percentages
    if re.search(r'\b[0-9]+\b|\%|\$', resume_text):
        evidence_score += 5
        
    # Look for common action verbs
    action_verbs = ['developed', 'created', 'managed', 'led', 'designed', 'improved', 'increased', 'reduced', 'implemented']
    for verb in action_verbs:
        if verb in resume_lower:
            evidence_score += 5
            break
            
    # Compute total
    ats_score = min(100, keyword_score + completeness_score + structure_score + role_alignment_score + evidence_score)
    
    return {
        "ats_score": ats_score,
        "keyword_score": keyword_score,
        "completeness_score": completeness_score,
        "structure_score": structure_score,
        "role_alignment_score": role_alignment_score,
        "evidence_score": evidence_score
    }
