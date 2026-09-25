# matcher.py
import re

PREDEFINED_SKILLS = [
    "Java", "Python", "C", "C++", "JavaScript", "TypeScript", "React",
    "Angular", "Vue", "Node.js", "Express.js", "Spring", "Spring Boot",
    "REST API", "HTML", "CSS", "SQL", "MySQL", "PostgreSQL", "MongoDB",
    "Git", "GitHub", "Docker", "AWS", "Azure", "Kubernetes",
    "Machine Learning", "Data Science", "FastAPI", "Django", "Flask",
    ".NET", "C#", "PHP"
]

def extract_skills(text: str) -> list:
    # Make it lowercase for case-insensitive matching
    text_lower = text.lower()
    
    # Replace punctuation (except our special skill characters) with spaces
    # This prevents 'Python,' from missing a match for 'Python'
    clean_text = re.sub(r'[^a-z0-9#\+.]', ' ', text_lower)
    
    # Add padding spaces to ensure exact word matches
    padded_text = " " + clean_text + " "
    
    found_skills = []
    for skill in PREDEFINED_SKILLS:
        skill_lower = skill.lower()
        
        # Check if the exact skill surrounded by spaces is in our text
        if " " + skill_lower + " " in padded_text:
            found_skills.append(skill)
            
    return found_skills

def match_skills(jd_text: str, resume_text: str, filename: str) -> dict:
    required_skills = extract_skills(jd_text)
    resume_skills = extract_skills(resume_text)
    
    matched_skills = [skill for skill in required_skills if skill in resume_skills]
    missing_skills = [skill for skill in required_skills if skill not in resume_skills]
    
    if len(required_skills) == 0:
        skill_match_percentage = 0
    else:
        skill_match_percentage = int((len(matched_skills) / len(required_skills)) * 100)
        
    return {
        "filename": filename,
        "required_skills": required_skills,
        "resume_skills": resume_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_match_percentage": skill_match_percentage
    }
