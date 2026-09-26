import os
import json
import re
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def analyze_resume_with_gemini(jd_text, resume_text, filename="resume"):
    prompt = f"""
    You are a Senior ATS Recruiter. Analyze this resume against this Job Description.

    JOB DESCRIPTION:
    {jd_text[:6000]}

    RESUME ({filename}):
    {resume_text[:6000]}

    TASK - You must return ONLY a valid JSON object, no extra text:

    {{
      "candidate_name": "extract from resume",
      "job_role": "role from JD",
      "ats_score": 85,
      "compatibility_score": 85,
      "rating": 8.5,
      "matched_skills": ["python", "sql", "django", "git"],
      "missing_skills": ["docker", "aws", "react"],
      "matched_pref_skills": ["agile"],
      "missing_pref_skills": [],
      "skill_coverage": 75,
      "breakdown_skills": 80,
      "breakdown_exp": 70,
      "breakdown_edu": 90,
      "breakdown_rel": 75,
      "breakdown_sections": 90,
      "breakdown_terminology": 80,
      "experience_alignment": "2 years relevant experience...",
      "education_alignment": "B.Tech CSE matches requirement...",
      "strengths": ["Strong in Python", "Good projects"],
      "improvement_suggestions": ["Learn Docker"],
      "recruitment_summary": "Highly suitable for JD2, shortlist...",
      "all_missing": ["docker", "aws"]
    }}

    RULES FOR QUALITY:
    1. ats_score = Calculate properly: Skills 40% + Keywords 20% + Education 15% + Experience 10% + Sections 10% + Terminology 5%. Be strict.
    2. matched_skills = Skills present in BOTH JD and Resume. Extract 5-10 technical skills. Lowercase.
    3. missing_skills = Required skills in JD but NOT in resume. Must be specific (e.g., javascript, react, html, css).
    4. If resume is Core Engineering / Mechanical, do NOT say missing is javascript - say missing is relevant engineering skills. Understand JD context.
    5. DO NOT return empty matched_skills. Always extract at least 3-5 skills from resume.
    6. recruitment_summary = 2 lines, specific to this resume vs this JD.
    7. Return ONLY JSON.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean markdown ```json ``` 
        text = re.sub(r"```json|```", "", text).strip()
        
        data = json.loads(text)
        
        # Ensure lists are not empty
        if not data.get("matched_skills"):
            data["matched_skills"] = ["communication", "problem solving"] # fallback, but Gemini should fill
        
        return data

    except Exception as e:
        print(f"Gemini Error for {filename}: {e}")
        # Fallback to local_analyzer result
        return {
            "error": str(e),
            "ats_score": 0,
            "matched_skills": [],
            "missing_skills": []
        }

def test_gemini_connection():
    try:
        model.generate_content("test")
        return True
    except:
        return False
