# HireMatch AI

HireMatch AI is an intelligent Telegram bot designed to streamline the recruitment process. It allows recruiters or hiring managers to upload a Job Description (JD) and candidate resumes to automatically evaluate and score them for compatibility. 

## Features
- **Telegram Bot Interface**: Easy-to-use conversational interface right inside Telegram.
- **Resume Parsing**: Supports extracting text from various document formats (PDF, DOCX, TXT, RTF, MD).
- **AI-Powered Analysis**: Utilizes Google's Gemini AI to deeply analyze the candidate's alignment with the role.
- **ATS Scoring System**: Calculates an Applicant Tracking System (ATS) score based on required skills, keyword coverage, education, and experience.
- **Detailed Evaluation Reports**: Provides a comprehensive breakdown including skill alignment (matched vs. missing), key strengths, and a recruitment summary.
- **Course Recommendations**: Suggests learning resources for candidates to bridge identified skill gaps.
- **Batch Processing**: Upload multiple resumes and analyze them all at once against the target Job Description.

## Project Structure
- **`telegram_bot.py`**: The core Telegram bot logic and message handlers.
- **`gemini_service.py`**: Integration with Google Gemini for AI-driven resume analysis.
- **`resume_parser.py`**: Utilities for extracting text from different file formats.
- **`local_analyzer.py` / `matcher.py` / `scorer.py`**: Local fallback logic for skill matching, keyword tracking, and ATS score calculation.
- **`course_recommender.py`**: Recommends relevant courses based on missing skills.

## How to Use
1. Start the bot on Telegram and send the `/start` command.
2. Send `/jd` and provide your Job Description (by uploading a file or pasting the text).
3. Send `/resume` and upload one or more candidate resumes.
4. Use `/analyze` to receive a detailed matching report for all uploaded candidates.
5. Use `/reset` to clear the current session and start a new evaluation.
