import os
import uuid
import re
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from resume_parser import extract_text_from_pdf, extract_text_from_docx, extract_text_from_txt, extract_resume_text
from matcher import match_skills
from gemini_service import analyze_resume_with_gemini
from scorer import calculate_ats_score
from course_recommender import get_recommendations

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)

sessions = {}

def get_session(user_id):
    if user_id not in sessions:
        sessions[user_id] = {
            "job_descriptions": [],
            "expected_file_type": None,
            "resumes": [],
            "failed_uploads": []
        }
    return sessions[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    sessions[user_id] = {
        "job_descriptions": [],
        "expected_file_type": None,
        "resumes": [],
        "failed_uploads": []
    }
    
    welcome_msg = (
        "Welcome to HireMatch AI.\n\n"
        "To get started, please tell me what you want to provide:\n"
        "• Send /jd to upload or paste a Job Description\n"
        "• Send /resume to upload resumes"
    )
    await update.message.reply_text(welcome_msg)

async def reset_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    sessions[user_id] = {
        "job_descriptions": [],
        "expected_file_type": None,
        "resumes": [],
        "failed_uploads": []
    }
    await update.message.reply_text(
        "SESSION RESET\n\n"
        "Your previous Job Description and resumes have been cleared.\n\n"
        "Please send a new Job Description to begin."
    )

async def list_resumes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    resumes = session.get("resumes", [])
    
    if not resumes:
        await update.message.reply_text("No resumes uploaded yet.")
        return
        
    msg = "Uploaded Resumes\n\n"
    for i, r in enumerate(resumes, 1):
        msg += f"{i}. {r['filename']}\n"
    msg += f"\nTotal: {len(resumes)} resumes"
    await update.message.reply_text(msg)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    
    document = update.message.document
    file_name = document.file_name.lower() if document.file_name else ""
    
    expected = session.get("expected_file_type")
    
    if expected is None:
        await update.message.reply_text(
            "Please tell me what you are uploading first:\n\n"
            "/jd - Upload a Job Description\n"
            "/resume - Upload candidate resumes"
        )
        return

    valid_extensions = (".pdf", ".docx", ".doc", ".txt", ".rtf", ".md")
    if not file_name.endswith(valid_extensions):
        if expected in ('resume', 'jd'):
            session.setdefault("failed_uploads", []).append(document.file_name or "Unknown File")
            return
        await update.message.reply_text("Please upload the file in a supported format (PDF, DOCX, TXT, RTF, MD).")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        ext = os.path.splitext(file_name)[1]
        unique_filename = f"file_{uuid.uuid4()}{ext}"
        file_path = os.path.join(UPLOADS_DIR, unique_filename)
        await file.download_to_drive(file_path)
    except Exception:
        if expected in ('resume', 'jd'):
            session.setdefault("failed_uploads", []).append(document.file_name or "Unknown File")
            return
        await update.message.reply_text("There was an error downloading your file. Please try again.")
        return

    if expected == 'jd':
        text = extract_resume_text(file_path)
        if not text or len(re.sub(r'[^a-zA-Z0-9]', '', text)) < 20:
            session.setdefault("failed_uploads", []).append(document.file_name or "Unknown File")
            return
            
        session.setdefault("job_descriptions", []).append({
            "filename": document.file_name,
            "text": text
        })
    elif expected == 'resume':
        resume_data = {
            "filename": document.file_name,
            "path": file_path
        }
        session["resumes"].append(resume_data)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    text = update.message.text.strip()
    text_lower = text.lower()
    
    # NLP support for analyzing a specific resume
    match = re.search(r"(?i)(check|analyze)\s*(only\s*)?resume\s*(\d+)", text)
    if match:
        context.args = [match.group(3)]
        await analyze(update, context)
        return

    if re.search(r"(?i)(check|analyze)\s*(only\s*)?one\s*resume", text):
        if len(session["resumes"]) == 1:
            context.args = ["1"]
            await analyze(update, context)
        elif len(session["resumes"]) > 1:
            await update.message.reply_text("Which resume would you like me to analyze? Please provide the resume number (e.g. /analyze 2).")
        else:
            await update.message.reply_text("Please upload at least one PDF or DOCX resume first.")
        return

    # Conversational Handling
    conversational_responses = {
        "hi": "Hi! Welcome to HireMatch AI. Send /jd to provide a Job Description, or /resume to provide resumes.",
        "hello": "Hello! Welcome to HireMatch AI. Send /jd to provide a Job Description, or /resume to provide resumes.",
        "hey": "Hey! Welcome to HireMatch AI. Send /jd to provide a Job Description, or /resume to provide resumes.",
        "good morning": "Good morning! Send /jd to provide a Job Description, or /resume to provide resumes.",
        "thanks": "You're welcome!",
        "thank you": "You're welcome! Let me know when you're ready to evaluate resumes.",
        "bye": "Goodbye! Feel free to come back whenever you're ready."
    }
    
    if text_lower in conversational_responses:
        if not session.get("job_description"):
            await update.message.reply_text(conversational_responses[text_lower])
        else:
            if text_lower in ["hi", "hello", "hey", "good morning"]:
                await update.message.reply_text("Hi! How can I help you?")
            else:
                await update.message.reply_text(conversational_responses[text_lower])
        return

    expected = session.get("expected_file_type")
    
    if expected == 'jd':
        session.setdefault("job_descriptions", []).append({
            "filename": "Pasted_JD_Text",
            "text": text
        })
    elif expected == 'resume':
        await update.message.reply_text("Please upload the resume as a file (PDF, DOCX, TXT, etc.).")
    else:
        # Check if they randomly pasted a JD without /jd
        jd_keywords = [
            "job title", "position", "role", 
            "responsibilities", "requirements", "qualifications", 
            "skills", "experience", "education", "location", 
            "technical skills"
        ]
        is_jd = any(keyword in text_lower for keyword in jd_keywords) and len(text_lower.split()) > 5
        
        if is_jd and not session.get("job_descriptions"):
            session.setdefault("job_descriptions", []).append({
                "filename": "Pasted_JD_Text",
                "text": text
            })
            await update.message.reply_text(
                "Job Description received successfully. Now send /resume to upload candidate resumes."
            )
        else:
            await update.message.reply_text(
                "Please tell me what you are uploading first:\n\n"
                "/jd - Upload a Job Description\n"
                "/resume - Upload candidate resumes"
            )

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    
    if not session.get("job_description"):
        await update.message.reply_text("Please provide the Job Description first.")
        return
        
    resumes = session.get("resumes", [])
    failed = session.get("failed_uploads", [])
    
    if not resumes and not failed:
        await update.message.reply_text("Please upload at least one PDF or DOCX resume first.")
        return
    elif not resumes and failed:
        await update.message.reply_text(f"0 resumes added. {len(failed)} file(s) could not be processed. Please upload valid resumes.")
        return
        
    targets = []
    if context.args and context.args[0].isdigit():
        idx = int(context.args[0])
        if 1 <= idx <= len(resumes):
            targets.append((idx, resumes[idx-1]))
        else:
            await update.message.reply_text(f"Resume {idx} not found. You have {len(resumes)} uploaded resumes.")
            return
    else:
        targets = list(enumerate(resumes, 1))
        
        # Summary message output
        total_received = len(resumes) + len(failed)
        if not failed:
            summary = f"{total_received} resume{'s' if total_received > 1 else ''} received successfully.\n\nFiles:\n"
            for i, r in enumerate(resumes, 1):
                summary += f"{i}. {r['filename']}\n"
            summary += "\nStarting analysis..."
        else:
            summary = f"{total_received} file{'s' if total_received > 1 else ''} received.\n"
            summary += f"{len(resumes)} resume{'s' if len(resumes) != 1 else ''} {'were' if len(resumes) != 1 else 'was'} successfully added.\n"
            summary += f"{len(failed)} file{'s' if len(failed) > 1 else ''} could not be processed:\n\n"
            for f in failed:
                summary += f"• {f}\n"
            summary += f"\nStarting analysis of {len(resumes)} resume{'s' if len(resumes) != 1 else ''}..."
        await update.message.reply_text(summary)
        
    num_targets = len(targets)
    progress_msg = None
    if num_targets > 1 and not context.args:
        progress_msg = await update.message.reply_text(
            f"<b>ANALYZING {num_targets} RESUMES...</b>\n\n"
            f"I found {num_targets} resumes.\n"
            f"I'll evaluate each resume against the uploaded Job Description.\n\n"
            f"Progress:\n0/{num_targets} completed",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"Analyzing {num_targets} resume(s) using HireMatch AI...\n\nThis may take a moment.")
    
    jd_text = session["job_description"]
    
    success_count = 0
    failed_count = 0
    
    for idx, r in targets:
        if progress_msg:
            try:
                await progress_msg.edit_text(
                    f"<b>ANALYZING {num_targets} RESUMES...</b>\n\n"
                    f"I found {num_targets} resumes.\n"
                    f"I'll evaluate each resume against the uploaded Job Description.\n\n"
                    f"Progress:\n{success_count + failed_count}/{num_targets} completed\n"
                    f"Analyzing resume {idx}/{num_targets}...",
                    parse_mode="HTML"
                )
            except Exception:
                pass
                
        try:
            print(f"\n[Resume {idx}] Parsing...")
            print(f"[Resume {idx}] Stored filename: {r.get('filename', 'Unknown')}")
            
            # Handle backward compatibility (if the user didn't /reset their old session)
            if "path" in r:
                path = r.get("path", "")
                print(f"[Resume {idx}] Path: {path}")
                if os.path.exists(path):
                    print(f"[Resume {idx}] File exists: True")
                    print(f"[Resume {idx}] Is file: {os.path.isfile(path)}")
                    print(f"[Resume {idx}] File size: {os.path.getsize(path)} bytes")
                    print(f"[Resume {idx}] Extension: {os.path.splitext(path)[1]}")
                else:
                    print(f"[Resume {idx}] File exists: False")
                
                resume_text = extract_resume_text(path)
            else:
                print(f"[Resume {idx}] Path: Missing (Legacy session state detected)")
                resume_text = r.get("text", "")
                
            print(f"[Resume {idx}] Extracted characters: {len(resume_text)}")
            
            if not resume_text.strip():
                failed_count += 1
                await update.message.reply_text(
                    f"<b>Resume #{idx}</b>\n"
                    f"Status: Analysis could not be completed.\n"
                    f"Reason: Resume content could not be extracted (file may be empty, unsupported, or scanned image).",
                    parse_mode="HTML"
                )
                continue
                
            from local_analyzer import analyze_resume_local
            local_result = analyze_resume_local(jd_text, resume_text)
            
            gemini_result = analyze_resume_with_gemini(jd_text, resume_text, r["filename"])
            
            if "error" in gemini_result:
                final_result = local_result
            else:
                final_result = local_result.copy()
            
            import html
            
            cand_name = html.escape(final_result.get("candidate_name", "Not specified"))
            job_role = html.escape(final_result.get("job_role", "Not specified"))
            comp_score = final_result.get("compatibility_score", 0)
            rating = final_result.get("rating", 0.0)
            ats_score = final_result.get("ats_score", 0)
            
            matched_req = final_result.get("matched_skills", [])
            matched_req_str = "\n".join([f"• {html.escape(s.title())}" for s in matched_req]) if matched_req else "• None"
            
            missing_req = final_result.get("missing_skills", [])
            missing_req_str = "\n".join([f"• {html.escape(s.title())}" for s in missing_req]) if missing_req else "• None"
            
            matched_pref = final_result.get("matched_pref_skills", [])
            matched_pref_str = "\n".join([f"• {html.escape(s.title())}" for s in matched_pref]) if matched_pref else "• None"
            
            missing_pref = final_result.get("missing_pref_skills", [])
            missing_pref_str = "\n".join([f"• {html.escape(s.title())}" for s in missing_pref]) if missing_pref else "• None"
            
            skill_coverage = final_result.get("skill_coverage", 0)
            
            breakdown_skills = final_result.get("breakdown_skills", 0)
            breakdown_exp = final_result.get("breakdown_exp", 0)
            breakdown_edu = final_result.get("breakdown_edu", 0)
            breakdown_rel = final_result.get("breakdown_rel", 0)
            breakdown_sec = final_result.get("breakdown_sections", 0)
            breakdown_term = final_result.get("breakdown_terminology", 0)
            
            exp_align = html.escape(final_result.get("experience_alignment", "Not specified"))
            edu_align = html.escape(final_result.get("education_alignment", "Not specified"))
            
            strengths = final_result.get("strengths", [])
            strengths_str = "\n".join([f"• {html.escape(s)}" for s in strengths]) if strengths else "• Not specified"
            
            improvements = final_result.get("improvement_suggestions", [])
            improvements_str = "\n".join([f"• {html.escape(s)}" for s in improvements]) if improvements else "• Not specified"
            
            recruit_summary = html.escape(final_result.get("recruitment_summary", "Not specified"))
            
            from course_recommender import get_recommendations
            recommendations = get_recommendations(final_result.get("all_missing", missing_req))
            if recommendations:
                rec_lines = []
                for rec_idx, rec in enumerate(recommendations, 1):
                    rec_lines.append(
                        f"<b>{rec_idx}. {html.escape(rec['title'])}</b>\n"
                        f"Recommended for: {html.escape(rec['recommended_for'].title())}\n"
                        f'<a href="{rec["url"]}">Start Learning</a>\n'
                    )
                rec_str = "\n".join(rec_lines)
            else:
                rec_str = "No major skill gaps identified based on the provided Job Description."
            
            ats_table = (
                "<b>ATS EVALUATION FRAMEWORK</b>\n\n"
                "• <b>Required skill/keyword match (40%)</b>\n  <i>How many important JD skills appear in the resume</i>\n"
                f"  Score: {breakdown_skills}%\n\n"
                "• <b>JD keyword coverage (20%)</b>\n  <i>Important terms from the JD appearing in the resume</i>\n"
                f"  Score: {breakdown_rel}%\n\n"
                "• <b>Education match (15%)</b>\n  <i>Degree/branch/education requirements</i>\n"
                f"  Score: {breakdown_edu}%\n\n"
                "• <b>Experience match (10%)</b>\n  <i>Fresher/experience requirements</i>\n"
                f"  Score: {breakdown_exp}%\n\n"
                "• <b>Resume sections (10%)</b>\n  <i>Skills, Education, Experience, Projects, etc.</i>\n"
                f"  Score: {breakdown_sec}%\n\n"
                "• <b>Terminology/relevance (5%)</b>\n  <i>Relevant role-specific terminology</i>\n"
                f"  Score: {breakdown_term}%\n\n"
                "Total = 100%"
            )
            
            report = (
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>RESUME {idx} OF {len(resumes)}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Candidate: <b>{cand_name}</b>\n"
                f"Target Role: <b>{job_role}</b>\n\n"
                "<b>OVERALL ASSESSMENT</b>\n\n"
                f"Compatibility Score: {comp_score}/100\n"
                f"ATS Compatibility: {ats_score}/100\n"
                f"Overall Rating: {rating}/10\n\n"
                f"{ats_table}\n\n"
                "<b>SKILL ALIGNMENT</b>\n\n"
                "<u>Required Skills</u>\n"
                "<b>Matched Skills</b>\n"
                f"{matched_req_str}\n"
                "<b>Missing Skills</b>\n"
                f"{missing_req_str}\n\n"
                "<u>Preferred / Additional Skills</u>\n"
                "<b>Matched</b>\n"
                f"{matched_pref_str}\n"
                "<b>Missing</b>\n"
                f"{missing_pref_str}\n\n"
                f"<b>Skill Coverage:</b> {skill_coverage}%\n\n"
                "<b>EXPERIENCE ALIGNMENT</b>\n\n"
                f"{exp_align}\n\n"
                "<b>EDUCATION ALIGNMENT</b>\n\n"
                f"{edu_align}\n\n"
                "<b>KEY STRENGTHS</b>\n\n"
                f"{strengths_str}\n\n"
                "<b>AREAS FOR IMPROVEMENT</b>\n\n"
                f"{improvements_str}\n\n"
                "<b>LEARNING RECOMMENDATIONS</b>\n\n"
                f"{rec_str}\n"
                "<b>RECRUITMENT SUMMARY</b>\n\n"
                f"{recruit_summary}"
            )
            
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for part in parts:
                    try:
                        await update.message.reply_text(part, parse_mode="HTML")
                    except Exception:
                        await update.message.reply_text(part)
            else:
                await update.message.reply_text(report, parse_mode="HTML")
                
            success_count += 1
                
        except Exception as e:
            failed_count += 1
            print(f"[Resume {idx}] Extraction/Analysis error: {e}")
            import traceback
            traceback.print_exc()
            await update.message.reply_text(
                f"<b>Resume #{idx}</b>\n"
                f"Status: Analysis could not be completed.\n"
                f"Reason: Resume content could not be extracted.",
                parse_mode="HTML"
            )

    if progress_msg:
        try:
            await progress_msg.edit_text(
                f"<b>ANALYZING {num_targets} RESUMES...</b>\n\n"
                f"I found {num_targets} resumes.\n"
                f"I'll evaluate each resume against the uploaded Job Description.\n\n"
                f"Progress:\n{success_count + failed_count}/{num_targets} completed",
                parse_mode="HTML"
            )
        except Exception:
            pass
            
    if num_targets > 1 and not context.args:
        if success_count == num_targets:
            msg = "Detailed evaluation reports have been generated for all uploaded resumes."
        elif success_count > 0:
            msg = f"Detailed evaluation reports have been generated for {success_count} of {num_targets} resumes."
        else:
            msg = "No evaluation reports could be generated because resume content could not be extracted."
            
        await update.message.reply_text(
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>BATCH ANALYSIS COMPLETED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Total Resumes: {num_targets}\n"
            f"Successfully Analyzed: {success_count}\n"
            f"Failed: {failed_count}\n\n"
            f"{msg}",
            parse_mode="HTML"
        )

async def cmd_jd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    session["expected_file_type"] = 'jd'
    await update.message.reply_text("Please upload the Job Description files (PDF, DOCX, TXT) or paste the text here. You can upload multiple JDs continuously.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    if not session.get("job_descriptions"):
        await update.message.reply_text("It is recommended to provide a Job Description first using /jd, but you can upload resumes now.")
    session["expected_file_type"] = 'resume'
    await update.message.reply_text("Please upload the candidate resumes. You can upload multiple resumes one after another.")

from gemini_service import analyze_resume_with_gemini, test_gemini_connection

def create_bot():
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set.")
    
    print("HireMatch AI Telegram Bot is running...")
    print("Gemini model: gemini-3.6-flash")
        
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_session))
    application.add_handler(CommandHandler("clear", reset_session))
    application.add_handler(CommandHandler("resumes", list_resumes))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(CommandHandler("jd", cmd_jd))
    application.add_handler(CommandHandler("resume", cmd_resume))
    
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return application