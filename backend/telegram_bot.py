import os
import uuid
import re
import traceback
import html
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from resume_parser import extract_resume_text
from gemini_service import analyze_resume_with_gemini
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

# --- COMMANDS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    sessions[user_id] = {"job_descriptions": [], "expected_file_type": None, "resumes": [], "failed_uploads": []}
    await update.message.reply_text(
        "Welcome to HireMatch AI.\n\n"
        "• Send /jd to upload Job Descriptions (you can upload MULTIPLE JDs)\n"
        "• Send /resume to upload resumes (bulk upload supported)\n"
        "• Send /analyze to get report\n\n"
        "If 1 JD = Detailed Report\nIf >1 JD = Comparison Table Report"
    )

async def reset_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    sessions[user_id] = {"job_descriptions": [], "expected_file_type": None, "resumes": [], "failed_uploads": []}
    await update.message.reply_text("SESSION RESET\nAll JDs and resumes cleared.")

async def cmd_jd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.from_user.id)
    session["expected_file_type"] = 'jd'
    await update.message.reply_text(f"Please upload JD file(s). Total JDs now: {len(session['job_descriptions'])}\nYou can upload multiple JDs one by one continuously.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = get_session(update.message.from_user.id)
    if not session.get("job_descriptions"):
        await update.message.reply_text("Tip: Provide JD first with /jd, but you can upload resumes now.")
    session["expected_file_type"] = 'resume'
    await update.message.reply_text(f"Please upload resumes. Already in queue: {len(session['resumes'])}\nKeep uploading, I will keep adding.")

# --- YOUR EXISTING HANDLERS (SAME, MINOR FIX) ---

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    document = update.message.document
    original_filename = document.file_name if document.file_name else "Unknown File"
    file_name = original_filename.lower()
    expected = session.get("expected_file_type")

    if expected is None:
        await update.message.reply_text("Please tell me what you are uploading first:\n\n/jd - Job Description\n/resume - Resumes")
        return

    if not file_name.endswith((".pdf", ".docx", ".doc", ".txt", ".rtf", ".md")):
        session.setdefault("failed_uploads", []).append(original_filename)
        await update.message.reply_text(f"Unsupported format: {original_filename}")
        return

    try:
        file = await context.bot.get_file(document.file_id)
        ext = os.path.splitext(file_name)[1]
        file_path = os.path.join(UPLOADS_DIR, f"file_{uuid.uuid4()}{ext}")
        await file.download_to_drive(file_path)
    except Exception as e:
        await update.message.reply_text(f"Download error: {str(e)}")
        return

    try:
        text = extract_resume_text(file_path)
        if not text or len(re.sub(r'[^a-zA-Z0-9]', '', text)) < 20:
            raise ValueError("Empty text extracted")
    except Exception as e:
        await update.message.reply_text(f"Could not process {original_filename}: {str(e)}")
        return
    finally:
        if os.path.exists(file_path) and expected == 'jd': # Keep resume path for re-extraction if needed
             pass

    if expected == 'jd':
        session["job_descriptions"].append({"filename": original_filename, "text": text})
        await update.message.reply_text(f"✅ JD {len(session['job_descriptions'])} received: {original_filename}\nTotal JDs: {len(session['job_descriptions'])}\nYou can add another JD or send /resume")
    else:
        session["resumes"].append({"filename": original_filename, "path": file_path, "text": text})
        await update.message.reply_text(f"✅ Resume added: {original_filename}\nTotal resumes: {len(session['resumes'])}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Keep your existing handle_text logic - pasted text as JD)
    user_id = update.message.from_user.id
    session = get_session(user_id)
    text = update.message.text.strip()
    expected = session.get("expected_file_type")

    if expected == 'jd' and len(text) > 20:
        session["job_descriptions"].append({"filename": "Pasted_JD_Text", "text": text})
        await update.message.reply_text(f"✅ JD {len(session['job_descriptions'])} saved (pasted text). Total JDs: {len(session['job_descriptions'])}")
    elif expected == 'resume':
        await update.message.reply_text("Please upload resume as file, not text.")
    else:
        await update.message.reply_text("Send /jd for JD or /resume for resumes first.")

# --- NEW UPGRADED ANALYZE WITH COMPARISON TABLE ---

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    session = get_session(user_id)
    jds = session.get("job_descriptions", [])
    resumes = session.get("resumes", [])

    if not jds:
        await update.message.reply_text("Provide JD first using /jd")
        return
    if not resumes:
        await update.message.reply_text("Upload resumes using /resume")
        return

    await update.message.reply_text(f"Analysis started.\nJDs: {len(jds)} | Resumes: {len(resumes)} | Total comparisons: {len(jds)*len(resumes)}")

    from local_analyzer import analyze_resume_local
    results_matrix = [] # List of {resume_name, scores: [ {jd_name, ats, matched, missing} ] }

    for r in resumes:
        resume_entry = {"resume_name": r["filename"], "comparisons": []}
        for jd_idx, jd in enumerate(jds):
            try:
                local_res = analyze_resume_local(jd["text"], r["text"])
                gemini_res = analyze_resume_with_gemini(jd["text"], r["text"], r["filename"])
                final = {**local_res, **gemini_res} if "error" not in gemini_res else local_res

                resume_entry["comparisons"].append({
                    "jd_name": jd["filename"],
                    "jd_idx": jd_idx+1,
                    "ats": final.get("ats_score", 0),
                    "matched": final.get("matched_skills", []),
                    "missing": final.get("missing_skills", []),
                    "full_report": final
                })
            except Exception as e:
                traceback.print_exc()
                resume_entry["comparisons"].append({"jd_name": jd["filename"], "jd_idx": jd_idx+1, "ats": 0, "matched": [], "missing": [], "full_report": {}})
        results_matrix.append(resume_entry)

    # ---- BUILD COMPARISON TABLE IF MULTI JD ----
    if len(jds) > 1:
        table = "<b>📊 COMPARISON TABLE - MULTI JD ANALYSIS</b>\n\n"
        table += "<pre>"
        header = f"{'Candidate':<20} |"
        for j in range(len(jds)):
            header += f" JD{j+1} ATS |"
        header += " Best Fit\n"
        table += header
        table += "-"*len(header) + "\n"

        for entry in results_matrix:
            row = f"{entry['resume_name'][:18]:<20} |"
            best_ats = -1
            best_jd = 1
            for comp in entry["comparisons"]:
                row += f" {comp['ats']:^7} |"
                if comp['ats'] > best_ats:
                    best_ats = comp['ats']
                    best_jd = comp['jd_idx']
            row += f" JD{best_jd} ({best_ats}%)\n"
            table += row
        table += "</pre>\n\n"

        # Detailed matched/missing per resume
        for entry in results_matrix:
            table += f"<b>{html.escape(entry['resume_name'])}</b>\n"
            for comp in entry["comparisons"]:
                matched_str = ", ".join(comp['matched'][:5]) if comp['matched'] else "None"
                missing_str = ", ".join(comp['missing'][:5]) if comp['missing'] else "None"
                table += f" JD{comp['jd_idx']} ({html.escape(comp['jd_name'])}): ATS {comp['ats']}/100\n"
                table += f" Matched: {html.escape(matched_str)}\n"
                table += f" Missing: {html.escape(missing_str)}\n"
            table += "\n"

        # Send table in chunks
        for i in range(0, len(table), 4000):
            await update.message.reply_text(table[i:i+4000], parse_mode="HTML")
    else:
        # Single JD detailed reports (your existing detailed report logic)
        for entry in results_matrix:
            comp = entry["comparisons"][0]
            full = comp["full_report"]
            report = (
                f"━━━━━━━━━━━━\n<b>{html.escape(entry['resume_name'])}</b>\n"
                f"JD: {html.escape(comp['jd_name'])}\n"
                f"ATS Score: {comp['ats']}/100\n"
                f"Matched: {html.escape(', '.join(comp['matched']))}\n"
                f"Missing: {html.escape(', '.join(comp['missing']))}\n\n"
                f"<b>Summary:</b> {html.escape(full.get('recruitment_summary',''))}\n"
            )
            await update.message.reply_text(report, parse_mode="HTML")

def create_bot():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset_session))
    application.add_handler(CommandHandler("clear", reset_session))
    application.add_handler(CommandHandler("jd", cmd_jd))
    application.add_handler(CommandHandler("resume", cmd_resume))
    application.add_handler(CommandHandler("analyze", analyze))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application