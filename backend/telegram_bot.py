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

    if not jds or not resumes:
        await update.message.reply_text("Need at least 1 JD and 1 resume")
        return

    print(f"[DEBUG] Starting analysis: {len(jds)} JDs x {len(resumes)} resumes")
    await update.message.reply_text(f"Analysis started.\nJDs: {len(jds)} | Resumes: {len(resumes)} | Comparisons: {len(jds)*len(resumes)}\nThis will take 20-30 sec...")

    from local_analyzer import analyze_resume_local
    from gemini_service import analyze_resume_with_gemini
    import asyncio

    results_matrix = []

    try:
        for r in resumes:
            entry = {"resume_name": r["filename"], "comparisons": []}
            for jd_idx, jd in enumerate(jds):
                try:
                    # 1. Local is fast - always works
                    local_res = analyze_resume_local(jd["text"], r["text"])
                    ats = local_res.get("ats_score", 0)
                    matched = local_res.get("matched_skills", [])
                    missing = local_res.get("missing_skills", [])

                    # 2. Gemini - try but don't crash if fails
                    try:
                        # Run gemini in thread so it doesn't block bot
                        gemini_res = await asyncio.to_thread(analyze_resume_with_gemini, jd["text"], r["text"], r["filename"])
                        if "error" not in gemini_res:
                            ats = gemini_res.get("ats_score", ats)
                            matched = gemini_res.get("matched_skills", matched)
                            missing = gemini_res.get("missing_skills", missing)
                    except Exception as g_err:
                        print(f"Gemini failed for {r['filename']} x JD{jd_idx+1}: {g_err}")
                        # Use local result only

                    entry["comparisons"].append({
                        "jd_name": jd["filename"],
                        "jd_idx": jd_idx+1,
                        "ats": ats,
                        "matched": matched,
                        "missing": missing
                    })
                    print(f"[OK] {r['filename']} vs JD{jd_idx+1} -> {ats}%")

                except Exception as e:
                    print(f"[FAIL] {r['filename']} vs JD{jd_idx+1}: {e}")
                    traceback.print_exc()
                    entry["comparisons"].append({"jd_name": jd["filename"], "jd_idx": jd_idx+1, "ats": 0, "matched": [], "missing": []})

            results_matrix.append(entry)

        # --- BUILD COMPARISON TABLE (GUARANTEED TO SEND) ---
        if len(jds) > 1:
            table = f"<b>📊 COMPARISON TABLE - {len(resumes)} Resumes vs {len(jds)} JDs</b>\n\n"
            table += "<pre>"
            header = f"{'Candidate':<18} |"
            for j in range(len(jds)): header += f" JD{j+1} |"
            header += " Best\n"
            table += header + "-"*40 + "\n"
            for entry in results_matrix:
                best = max(entry["comparisons"], key=lambda x: x["ats"])
                row = f"{entry['resume_name'][:16]:<18} |"
                for comp in entry["comparisons"]:
                    row += f" {comp['ats']:>3}% |"
                row += f" JD{best['jd_idx']}\n"
                table += row
            table += "</pre>\n\n"

            for entry in results_matrix:
                table += f"<b>{html.escape(entry['resume_name'])}</b>\n"
                for comp in entry["comparisons"]:
                    table += f" JD{comp['jd_idx']}: ATS {comp['ats']} | Matched: {', '.join(comp['matched'][:4])} | Missing: {', '.join(comp['missing'][:4])}\n"
                table += "\n"

            await update.message.reply_text(table[:4000], parse_mode="HTML")
            if len(table) > 4000:
                await update.message.reply_text(table[4000:8000], parse_mode="HTML")
        else:
            # Single JD report
            for entry in results_matrix:
                comp = entry["comparisons"][0]
                msg = f"<b>{html.escape(entry['resume_name'])}</b>\nATS: {comp['ats']}/100\nMatched: {html.escape(', '.join(comp['matched']))}\nMissing: {html.escape(', '.join(comp['missing']))}"
                await update.message.reply_text(msg, parse_mode="HTML")

        await update.message.reply_text("✅ Analysis Complete. Send /reset for new session.")

    except Exception as main_e:
        print(f"[CRITICAL ERROR in analyze]: {main_e}")
        traceback.print_exc()
        await update.message.reply_text(f"Analysis failed: {str(main_e)}\nCheck terminal logs. But your resumes were parsed. Try again with /analyze")

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