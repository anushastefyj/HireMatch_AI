import os
import json
import time
from google import genai
from google.genai import errors

def test_gemini_connection() -> bool:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return False
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents="Reply with OK."
        )
        return response.text is not None
    except Exception:
        return False

def analyze_resume_with_gemini(jd_text: str, resume_text: str, filename: str = "Unknown") -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error_type": "config", "error": "AI analysis configuration needs attention."}

    if not resume_text or len(resume_text.strip()) < 20:
        return {"error_type": "extraction", "error": "Unable to extract readable text from this resume."}

    client = genai.Client(api_key=api_key)
    
    prompt = f"""You are a professional recruitment assistant.

Analyze the candidate's resume against the Job Description.

EVALUATION CRITERIA:
1. Strict Evidence: Only include a skill in "matched_skills" if there is ACTUAL evidence of it in the resume text. Do not assume related skills. (e.g. Java does not imply Selenium). 
2. Missing Skills: Only include important requirements from the JD that are genuinely missing or not demonstrated. Do not list random unrelated skills. Separate required vs preferred if clear, otherwise just list them.
3. Strict Truthfulness: Base all conclusions ONLY on the provided text. Do not invent skills, experience, or certifications. If information is missing, state it is not specified.

Return ONLY valid JSON using the exact structure requested below.

Requested JSON structure:
{{
    "candidate_name": "Extract if present, else 'Not specified'",
    "job_role": "Extract from JD",
    "compatibility_score": 0,
    "rating": 0.0,
    "matched_skills": ["Java", "MySQL"],
    "missing_skills": ["Manual Testing", "Test Case Creation"],
    "skill_match_summary": "2-3 professional sentences explaining the alignment.",
    "experience_alignment": "Professional analysis of experience.",
    "education_alignment": "Professional analysis of education.",
    "strengths": ["...", "..."],
    "improvement_suggestions": ["...", "..."],
    "recruitment_summary": "3-5 professional sentences on overall alignment. Do not make an absolute hiring decision."
}}

Calculate compatibility_score out of 100 based on exact skill matching, experience relevance, and completeness.
Rating must be compatibility_score / 10.

---
JOB DESCRIPTION:
{jd_text}

---
RESUME:
{resume_text}
"""

    retries = [3, 6, 12]
    attempt = 0
    
    while attempt <= len(retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt,
            )
            
            raw_text = response.text.strip()
            
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
                
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
                
            raw_text = raw_text.strip()
            return json.loads(raw_text)
            
        except json.JSONDecodeError:
            return {"error_type": "temporary", "error": "AI analysis is temporarily unavailable for this resume.\nPlease try again later."}
            
        except Exception as e:
            err_msg = str(e).lower()
            
            # Identify error type and status if possible
            err_type = type(e).__name__
            status_code = getattr(e, 'code', 'Unknown')
            
            print(f"Gemini analysis failed for: {filename}")
            print(f"Attempt: {attempt+1}/{len(retries)+1}")
            print(f"Error type: {err_type}")
            print(f"Status: {status_code}")
            
            # Do not retry permanent errors
            is_config = any(code in err_msg for code in ["404", "401", "403", "api key", "not found", "permission denied", "invalid request", "400"])
            
            if is_config or str(status_code) in ["400", "401", "403", "404"]:
                return {"error_type": "config", "error": "AI analysis configuration needs attention."}
                
            # Temporary errors: 429, 500, 502, 503, 504
            is_temporary = any(code in err_msg for code in ["429", "500", "502", "503", "504", "unavailable", "too many requests"])
            if str(status_code) in ["429", "500", "502", "503", "504"]:
                is_temporary = True
                
            if is_temporary:
                if attempt < len(retries):
                    time.sleep(retries[attempt])
                    attempt += 1
                else:
                    print(f"Gemini analysis failed for {filename} after {len(retries)+1} attempts.")
                    return {"error_type": "temporary", "error": "AI analysis is temporarily unavailable for this resume.\nPlease try again later."}
            else:
                # Unhandled error, still retry if it might be network
                if attempt < len(retries):
                    time.sleep(retries[attempt])
                    attempt += 1
                else:
                    print(f"Gemini analysis failed for {filename} after {len(retries)+1} attempts.")
                    return {"error_type": "temporary", "error": "AI analysis is temporarily unavailable for this resume.\nPlease try again later."}

    return {"error_type": "temporary", "error": "AI analysis is temporarily unavailable for this resume.\nPlease try again later."}
