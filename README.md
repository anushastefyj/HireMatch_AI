# HireMatch AI

HireMatch AI is an intelligent Telegram bot designed to streamline the recruitment process. It allows recruiters to upload **Multiple Job Descriptions (JDs)** and **Multiple Resumes** at once and automatically evaluates compatibility with ATS scoring and side-by-side comparison.

## 🚀 What's New - Updated Flow
- **Intent-Based Upload**: No more "first file = JD" confusion. Bot now asks what you are uploading.
- **Multiple JD Support**: You can upload more than 1 JD to compare which candidate fits which role best.
- **Comparison Table Mode**: If >1 JD is provided, the bot auto-switches to a comparison table format showing each resume's score against each JD.
- **Bulk Resume Handling**: Once you send `/resume`, you can upload 10+ resumes back-to-back without retyping the command.

## Features
- **Telegram Bot Interface**: Easy conversational flow with `/jd`, `/resume`, `/analyze` commands.
- **Smart State Tracking**: Tracks `expected_file_type` to know if next file is a JD or a Resume.
- **Resume Parsing**: Supports PDF, DOCX, TXT, RTF, MD.
- **AI-Powered Analysis**: Uses Google Gemini AI for deep skill alignment beyond keyword matching.
- **Advanced ATS Scoring**: Calculates score out of 100 based on Skills (50%), Experience (20%), Education (15%), Keywords (15%).
- **Detailed Reports**: For each candidate: Matched Skills, Missing Skills, Strengths, Verdict, Course Recommendations.
- **Comparison Table Report**: When multiple JDs are present -> `| Candidate | JD1 ATS | JD2 ATS | Matched | Missing | Best Fit |`
- **Course Recommendations**: Suggests courses for missing skills.

## Project Structure
- **`telegram_bot.py`**: Core bot logic, handles `/jd`, `/resume`, `/analyze`, `/reset` and state tracking `expected_file_type`.
- **`gemini_service.py`**: Gemini integration with new prompt for multi-JD comparison table logic.
- **`resume_parser.py`**: Text extraction from all formats.
- **`local_analyzer.py` / `scorer.py`**: Fallback ATS calculation.
- **`course_recommender.py`**: Maps missing skills to courses.

## How to Use - New Flow
1. Start bot -> `/start`
2. Send `/jd` -> Upload JD file(s). You can send `/jd` again to add a 2nd or 3rd JD for comparison. Bot says "JD 1 saved", "JD 2 saved".
3. Send `/resume` -> Now upload all candidate resumes one by one. Bot will keep adding them.
4. Send `/analyze` -> 
   - If 1 JD: Get detailed report per resume (ATS, Matched/Missing skills, Summary)
   - If >1 JD: Get comparison table showing each resume's score vs each JD + Final Recommendation (Best JD for each candidate)
5. `/reset` to clear session.

## Example Output
| Candidate | JD 1: Python Dev | JD 2: Data Analyst | Verdict |
| :--- | :--- | :--- | :--- |
| Ramesh.pdf | 82% | 45% | Best for JD 1 |
| Priya.docx | 55% | 91% | Best for JD 2 |
