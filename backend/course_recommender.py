# course_recommender.py

COURSE_CATALOG = {
    "istqb": {
        "title": "ISTQB Certified Tester Foundation Level (CTFL) v4.0",
        "url": "https://www.istqb.org/certifications/certified-tester-foundation-level-ctfl-v4-0/",
        "why": "Builds a foundation in software testing concepts, test techniques, test management and defect management."
    },
    "java": {
        "title": "Java Programming Tutorials",
        "url": "https://dev.java/learn/",
        "why": "Official comprehensive guide to mastering Java fundamentals and advanced concepts."
    },
    "python": {
        "title": "Python Tutorial",
        "url": "https://docs.python.org/3/tutorial/",
        "why": "The official standard resource for learning Python programming from the creators."
    },
    "javascript": {
        "title": "JavaScript Guide",
        "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
        "why": "MDN is the industry standard documentation for learning JavaScript."
    },
    "react": {
        "title": "React Learn",
        "url": "https://react.dev/learn",
        "why": "Official React documentation for learning modern component-based UI development."
    },
    "node.js": {
        "title": "Node.js Learn",
        "url": "https://nodejs.org/en/learn/",
        "why": "Official Node.js resource to understand server-side JavaScript execution."
    },
    "spring boot": {
        "title": "Spring Guides",
        "url": "https://spring.io/guides",
        "why": "Official Spring Boot tutorials for building robust enterprise Java applications."
    },
    "sql": {
        "title": "SQL Tutorial",
        "url": "https://www.w3schools.com/sql/",
        "why": "A beginner-friendly and practical guide to relational databases and queries."
    },
    "machine learning": {
        "title": "Machine Learning Crash Course",
        "url": "https://developers.google.com/machine-learning/crash-course",
        "why": "A fast-paced, practical introduction to ML fundamentals by Google."
    },
    "gemini api": {
        "title": "Gemini API Documentation",
        "url": "https://ai.google.dev/gemini-api/docs",
        "why": "Official Google guides on integrating the Gemini LLM into applications."
    },
    "fastapi": {
        "title": "FastAPI Tutorial",
        "url": "https://fastapi.tiangolo.com/tutorial/",
        "why": "Official and highly acclaimed tutorial for building fast APIs in Python."
    },
    "git": {
        "title": "Git Documentation",
        "url": "https://git-scm.com/doc",
        "why": "The definitive resource for version control workflows."
    },
    "mongodb": {
        "title": "MongoDB Documentation",
        "url": "https://www.mongodb.com/docs/",
        "why": "Official NoSQL database documentation covering architecture and queries."
    }
}

KEYWORD_MAP = {
    "manual testing": "istqb",
    "testing": "istqb",
    "software testing": "istqb",
    "test cases": "istqb",
    "test case creation": "istqb",
    "defect tracking": "istqb",
    "defect management": "istqb",
    "sit": "istqb",
    "uat": "istqb",
    "sit/uat": "istqb",
    "requirement traceability matrix": "istqb",
    "rtm": "istqb",
    "selenium": "istqb",
    "java": "java",
    "core java": "java",
    "python": "python",
    "javascript": "javascript",
    "typescript": "javascript",
    "react": "react",
    "node.js": "node.js",
    "spring boot": "spring boot",
    "sql": "sql",
    "mysql": "sql",
    "machine learning": "machine learning",
    "google gemini api": "gemini api",
    "fastapi": "fastapi",
    "git": "git",
    "github": "git",
    "mongodb": "mongodb"
}

def get_recommendations(missing_skills: list) -> list:
    course_to_skills = {}
    
    for skill in missing_skills:
        skill_lower = skill.lower().strip()
        
        found_course_id = None
        
        # Exact match
        if skill_lower in KEYWORD_MAP:
            found_course_id = KEYWORD_MAP[skill_lower]
        else:
            # Partial match
            for keyword, course_id in KEYWORD_MAP.items():
                # Prevent "c" from matching "defect tracking"
                if keyword in skill_lower:
                    found_course_id = course_id
                    break
        
        if found_course_id:
            if found_course_id not in course_to_skills:
                course_to_skills[found_course_id] = []
            if skill not in course_to_skills[found_course_id]:
                course_to_skills[found_course_id].append(skill)
                
    recommendations = []
    
    for course_id, skills_mapped in list(course_to_skills.items())[:3]:
        course = COURSE_CATALOG[course_id]
        recommendations.append({
            "title": course["title"],
            "url": course["url"],
            "why": course["why"],
            "recommended_for": ", ".join(skills_mapped)
        })
        
    return recommendations
