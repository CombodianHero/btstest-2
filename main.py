"""
Bridge to Success — Telegram Bot Extractor
Deployment: Koyeb (Web Service with health-check server)
"""

import os
import logging
import asyncio
import threading
import requests
import json
import time
import sys

from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION  — set BOT_TOKEN as environment variable on Koyeb dashboard
# ─────────────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ── API Constants ─────────────────────────────────────────────────────────────
BASE_URL    = "https://bridgetosuccess.learncentre.tech"
API_BASE    = f"{BASE_URL}/public/study_api_sprint13_security_promo/"
STORAGE_PDF = f"{BASE_URL}/public/storage/pdf/"
STORAGE_VID = f"{BASE_URL}/public/storage/video/"
STORAGE_IMG = f"{BASE_URL}/public/storage/course/"
PLAYER_URL  = "https://lctplayer.learncentre.online/v/player.php?v="
LIVE_URL    = "https://lctplayer.learncentre.online/live/live_player.php?v="

# ── Discovered API Endpoints ──────────────────────────────────────────────────
ENDPOINTS = {
    # Auth
    "send_otp"         : "send-otp",
    "verify_otp"       : "verify-otp",
    "register"         : "register",
    "login"            : "login",
    # Home / Dashboard
    "home"             : "get-home-data",
    "slider"           : "get-slider",
    "notifications"    : "get-notifications",
    "profile"          : "get-profile",
    # Courses & Batches
    "all_courses"      : "get-all-courses",
    "my_courses"       : "get-my-courses",
    "top_courses"      : "get-top-courses",
    "course_detail"    : "get-course-detail",
    "categories"       : "get-categories",
    "category_courses" : "get-category-courses",
    # Batch / Subject / Chapter
    "batch_list"       : "get-batch-list",
    "subject_list"     : "get-subject-list",
    "chapter_list"     : "get-chapter-list",
    "topic_list"       : "get-topic-list",
    # Videos
    "video_list"       : "get-video-list",
    "video_detail"     : "get-video-detail",
    "free_videos"      : "get-free-video",
    # PDFs / Notes
    "pdf_list"         : "get-pdf-list",
    "pdf_detail"       : "get-pdf-detail",
    "free_pdfs"        : "get-free-pdf",
    # Live Classes
    "live_classes"     : "get-live-class",
    "live_stream"      : "get-live-stream",
    # EBooks
    "ebook_list"       : "get-ebook-list",
    "ebook_series"     : "get-ebook-series",
    # Tests
    "test_series"      : "get-test-series",
    "test_list"        : "get-test-list",
    "test_detail"      : "get-test-detail",
    # Doubts / Tickets
    "doubt_courses"    : "get-doubt-courses",
    "doubt_list"       : "get-doubt-list",
    "ticket_list"      : "get-ticket-list",
    # Mixed content
    "mixed_content"    : "get-mixed-content",
    # News / Board Results
    "news"             : "get-news",
    "board_result"     : "get-board-result",
    # Events
    "events"           : "get-events",
    "event_video"      : "get-event-video",
    # Downloads
    "download_list"    : "get-download-list",
    # Shop / Cart
    "cart"             : "get-cart",
    "purchase"         : "purchase-course",
    "enroll_free"      : "enroll-free-course",
}

# ─────────────────────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION MANAGER
# ─────────────────────────────────────────────────────────────────────────────
user_sessions: dict = {}


def get_headers(user_id: int) -> dict:
    headers = {
        "Content-Type" : "application/json",
        "Accept"       : "application/json",
        "User-Agent"   : "okhttp/4.9.3",
        "Connection"   : "keep-alive",
    }
    if user_id in user_sessions and user_sessions[user_id].get("token"):
        headers["Authorization"] = f"Bearer {user_sessions[user_id]['token']}"
        headers["authtoken"]     = user_sessions[user_id]["token"]
    return headers


def api_post(endpoint_key: str, data: dict, user_id: int = 0) -> dict:
    url = API_BASE + ENDPOINTS.get(endpoint_key, endpoint_key)
    try:
        resp = requests.post(url, json=data, headers=get_headers(user_id), timeout=20, verify=True)
        return resp.json()
    except Exception as e:
        logger.error(f"API POST error [{endpoint_key}]: {e}")
        return {"status": 0, "message": str(e)}


def api_get(endpoint_key: str, params: dict = None, user_id: int = 0) -> dict:
    url = API_BASE + ENDPOINTS.get(endpoint_key, endpoint_key)
    try:
        resp = requests.get(url, params=params, headers=get_headers(user_id), timeout=20, verify=True)
        return resp.json()
    except Exception as e:
        logger.error(f"API GET error [{endpoint_key}]: {e}")
        return {"status": 0, "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# LINK EXTRACTORS
# ─────────────────────────────────────────────────────────────────────────────

def extract_video_url(video_data: dict) -> str:
    fields = [
        "video_url", "videoUrl", "videoLink", "video_link",
        "hls_url", "stream_url", "url", "file_url",
        "dash_url", "mp4_url", "link"
    ]
    for f in fields:
        val = video_data.get(f)
        if val and isinstance(val, str) and len(val) > 5:
            if val.startswith("storage/"):
                return STORAGE_VID + val.replace("storage/video/", "")
            if val.startswith("http"):
                return val
            if val.isdigit() or (len(val) < 30 and "/" not in val):
                return PLAYER_URL + val
    vid_id = video_data.get("video_id") or video_data.get("videoId") or video_data.get("id")
    if vid_id:
        return PLAYER_URL + str(vid_id)
    return "URL_NOT_FOUND"


def extract_pdf_url(pdf_data: dict) -> str:
    fields = [
        "pdf_url", "pdfUrl", "pdf_link", "file_url", "url",
        "pdf_file", "file", "link", "pdf_path"
    ]
    for f in fields:
        val = pdf_data.get(f)
        if val and isinstance(val, str) and len(val) > 3:
            if val.startswith("storage/"):
                return BASE_URL + "/public/" + val
            if val.startswith("http"):
                return val
            if not val.startswith("/"):
                return STORAGE_PDF + val
    pdf_name = pdf_data.get("pdf_name") or pdf_data.get("name") or pdf_data.get("pdf_id")
    if pdf_name:
        return STORAGE_PDF + str(pdf_name)
    return "URL_NOT_FOUND"


# ─────────────────────────────────────────────────────────────────────────────
# CONTENT FETCHERS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_all_batches(token: str, user_id: int) -> list:
    results = []

    my_courses_resp = api_get("my_courses", user_id=user_id)
    courses = []
    if my_courses_resp.get("status") == 1:
        courses = my_courses_resp.get("data", [])
        if isinstance(courses, dict):
            courses = list(courses.values())
    logger.info(f"Found {len(courses)} enrolled courses")

    all_courses_resp = api_get("all_courses", user_id=user_id)
    if all_courses_resp.get("status") == 1:
        all_c = all_courses_resp.get("data", [])
        if isinstance(all_c, dict):
            all_c = list(all_c.values())
        existing_ids = {c.get("id") or c.get("course_id") for c in courses}
        for c in all_c:
            cid = c.get("id") or c.get("course_id")
            if cid not in existing_ids:
                courses.append(c)

    for course in courses:
        course_id   = course.get("id") or course.get("course_id")
        course_name = course.get("name") or course.get("course_name") or f"Course-{course_id}"
        logger.info(f"Processing course: {course_name} ({course_id})")

        batch_resp = api_post("batch_list", {"course_id": course_id}, user_id=user_id)
        batches = batch_resp.get("data", [])
        if isinstance(batches, dict):
            batches = list(batches.values())
        if not batches:
            detail_resp = api_post("course_detail", {"course_id": course_id}, user_id=user_id)
            batches = detail_resp.get("data", {}).get("batch", []) or []

        for batch in batches:
            batch_id   = batch.get("id") or batch.get("batch_id")
            batch_name = batch.get("name") or batch.get("batch_name") or f"Batch-{batch_id}"

            subject_resp = api_post(
                "subject_list",
                {"course_id": course_id, "batch_id": batch_id},
                user_id=user_id
            )
            subjects = subject_resp.get("data", [])
            if isinstance(subjects, dict):
                subjects = list(subjects.values())

            for subject in subjects:
                subject_id   = subject.get("id") or subject.get("subject_id")
                subject_name = subject.get("name") or subject.get("subject_name") or f"Subject-{subject_id}"

                chapter_resp = api_post(
                    "chapter_list",
                    {"course_id": course_id, "batch_id": batch_id, "subject_id": subject_id},
                    user_id=user_id
                )
                chapters = chapter_resp.get("data", [])
                if isinstance(chapters, dict):
                    chapters = list(chapters.values())

                for chapter in chapters:
                    chapter_id   = chapter.get("id") or chapter.get("chapter_id")
                    chapter_name = chapter.get("name") or chapter.get("chapter_name") or f"Chapter-{chapter_id}"

                    # Videos
                    video_resp = api_post(
                        "video_list",
                        {"course_id": course_id, "batch_id": batch_id,
                         "subject_id": subject_id, "chapter_id": chapter_id},
                        user_id=user_id
                    )
                    videos = video_resp.get("data", [])
                    if isinstance(videos, dict):
                        videos = list(videos.values())
                    for video in videos:
                        results.append({
                            "type"       : "VIDEO",
                            "course"     : course_name,
                            "batch"      : batch_name,
                            "subject"    : subject_name,
                            "chapter"    : chapter_name,
                            "title"      : video.get("title") or video.get("name") or "Untitled",
                            "url"        : extract_video_url(video),
                            "duration"   : video.get("duration") or video.get("video_duration") or "",
                            "video_type" : video.get("video_type") or video.get("type") or "unknown",
                        })

                    # PDFs
                    pdf_resp = api_post(
                        "pdf_list",
                        {"course_id": course_id, "batch_id": batch_id,
                         "subject_id": subject_id, "chapter_id": chapter_id},
                        user_id=user_id
                    )
                    pdfs = pdf_resp.get("data", [])
                    if isinstance(pdfs, dict):
                        pdfs = list(pdfs.values())
                    for pdf in pdfs:
                        results.append({
                            "type"    : "PDF",
                            "course"  : course_name,
                            "batch"   : batch_name,
                            "subject" : subject_name,
                            "chapter" : chapter_name,
                            "title"   : pdf.get("title") or pdf.get("name") or "Untitled",
                            "url"     : extract_pdf_url(pdf),
                        })

                    time.sleep(0.3)

    return results


def fetch_free_content(user_id: int = 0) -> list:
    results = []

    fv_resp = api_get("free_videos", user_id=user_id)
    free_vids = fv_resp.get("data", [])
    if isinstance(free_vids, dict):
        free_vids = list(free_vids.values())
    for v in free_vids:
        results.append({
            "type"   : "FREE_VIDEO",
            "title"  : v.get("title") or v.get("name") or "Free Video",
            "url"    : extract_video_url(v),
            "course" : v.get("course_name") or "Free",
        })

    fp_resp = api_get("free_pdfs", user_id=user_id)
    free_pdfs = fp_resp.get("data", [])
    if isinstance(free_pdfs, dict):
        free_pdfs = list(free_pdfs.values())
    for p in free_pdfs:
        results.append({
            "type"   : "FREE_PDF",
            "title"  : p.get("title") or p.get("name") or "Free PDF",
            "url"    : extract_pdf_url(p),
            "course" : p.get("course_name") or "Free",
        })

    return results


def format_content_list(items: list, max_chars: int = 4000) -> list:
    chunks = []
    current = ""
    for i, item in enumerate(items, 1):
        icon = "🎬" if "VIDEO" in item["type"] else "📄"
        line = (
            f"{icon} *{i}. {item['title']}*\n"
            f"   📂 {item.get('course','')}"
        )
        if item.get("batch"):
            line += f" → {item['batch']}"
        if item.get("subject"):
            line += f"\n   📌 {item['subject']}"
        if item.get("chapter"):
            line += f" → {item['chapter']}"
        line += f"\n   🔗 `{item['url']}`\n\n"

        if len(current) + len(line) > max_chars:
            chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)
    return chunks if chunks else ["No content found."]


# ─────────────────────────────────────────────────────────────────────────────
# BOT HANDLERS
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔑 Login (OTP)", callback_data="menu_login")],
        [InlineKeyboardButton("🆓 Free Content (No Login)", callback_data="menu_free")],
        [InlineKeyboardButton("📦 Extract All Batches", callback_data="menu_batches")],
        [InlineKeyboardButton("🎬 All Videos Only", callback_data="menu_videos")],
        [InlineKeyboardButton("📄 All PDFs Only", callback_data="menu_pdfs")],
        [InlineKeyboardButton("ℹ️ App Info & Loopholes", callback_data="menu_info")],
        [InlineKeyboardButton("🚪 Logout", callback_data="menu_logout")],
    ]
    await update.message.reply_text(
        "🎓 *Bridge to Success — Content Extractor*\n\n"
        "This bot can extract all batch videos and PDFs from the app.\n\n"
        "Choose an option below:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Commands*\n\n"
        "/start — Main menu\n"
        "/login — Login with mobile OTP\n"
        "/free — Get free content (no login needed)\n"
        "/batches — Extract all batch content\n"
        "/videos — Get all video links\n"
        "/pdfs — Get all PDF links\n"
        "/info — App analysis & security loopholes\n"
        "/logout — Clear your session\n",
        parse_mode="Markdown"
    )


async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login_step"] = "awaiting_mobile"
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    await msg.reply_text(
        "📱 Enter your registered *mobile number* (10 digits, no country code):",
        parse_mode="Markdown"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text.strip()
    step = context.user_data.get("login_step", "")

    if step == "awaiting_mobile":
        if not text.isdigit() or len(text) != 10:
            await update.message.reply_text("❌ Invalid number. Enter 10-digit mobile (no spaces).")
            return
        context.user_data["mobile"]     = text
        context.user_data["login_step"] = "awaiting_otp"

        resp = api_post("send_otp", {"mobile": text, "type": "login"})
        if resp.get("status") == 1:
            await update.message.reply_text(
                f"✅ OTP sent to {text}.\nNow enter the *OTP* you received:",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Could not send OTP: {resp.get('message','Unknown error')}\n"
                "Trying register endpoint..."
            )
            resp2 = api_post("send_otp", {"mobile": text, "type": "register"})
            if resp2.get("status") == 1:
                await update.message.reply_text("✅ OTP sent! Enter it below:")
            else:
                await update.message.reply_text(f"❌ Failed: {resp2.get('message','Error')}")
                context.user_data["login_step"] = ""

    elif step == "awaiting_otp":
        mobile = context.user_data.get("mobile", "")
        if not text.isdigit():
            await update.message.reply_text("❌ OTP must be digits only.")
            return

        resp = api_post("login", {"mobile": mobile, "otp": text})
        if resp.get("status") != 1:
            resp = api_post("verify_otp", {"mobile": mobile, "otp": text})

        if resp.get("status") == 1:
            data    = resp.get("data", {})
            token   = (
                data.get("token") or data.get("authtoken") or
                data.get("api_token") or data.get("access_token") or ""
            )
            user_id = data.get("id") or data.get("user_id") or data.get("userId") or ""
            name    = data.get("name") or data.get("full_name") or mobile

            user_sessions[uid] = {
                "token"   : token,
                "user_id" : str(user_id),
                "mobile"  : mobile,
                "name"    : name,
            }
            context.user_data["login_step"] = ""
            await update.message.reply_text(
                f"✅ *Logged in as {name}!*\n\nNow use /batches to extract all content.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ Login failed: {resp.get('message','Wrong OTP or account not found.')}"
            )
            context.user_data["login_step"] = ""

    else:
        await update.message.reply_text(
            "Use /start to see the menu or /login to authenticate."
        )


async def get_free_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    await msg.reply_text("🔍 Fetching free content (no login required)...")

    uid   = update.effective_user.id
    items = fetch_free_content(user_id=uid)

    if not items:
        await msg.reply_text(
            "ℹ️ No free content returned. The server may require login even for free items.\n"
            "Try /login first."
        )
        return

    await msg.reply_text(f"✅ Found *{len(items)}* free items:", parse_mode="Markdown")
    for chunk in format_content_list(items):
        await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)


async def get_all_batches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )

    if uid not in user_sessions:
        await msg.reply_text("⚠️ You must /login first.")
        return

    session = user_sessions[uid]
    await msg.reply_text(
        f"⚙️ Extracting all batch content for *{session['name']}*...\n"
        "_This may take a few minutes depending on how many courses you have._",
        parse_mode="Markdown"
    )

    try:
        items = fetch_all_batches(session["token"], uid)
    except Exception as e:
        await msg.reply_text(f"❌ Error during extraction: {e}")
        return

    if not items:
        await msg.reply_text(
            "⚠️ No content found. Possible reasons:\n"
            "• No enrolled courses\n"
            "• API response structure differs\n"
            "• Token expired — try /login again"
        )
        return

    videos = [i for i in items if "VIDEO" in i["type"]]
    pdfs   = [i for i in items if "PDF"   in i["type"]]

    await msg.reply_text(
        f"✅ *Extraction Complete!*\n\n"
        f"🎬 Videos : {len(videos)}\n"
        f"📄 PDFs   : {len(pdfs)}\n"
        f"📦 Total  : {len(items)}\n\nSending links now...",
        parse_mode="Markdown"
    )

    if videos:
        await msg.reply_text("*🎬 VIDEO LINKS:*", parse_mode="Markdown")
        for chunk in format_content_list(videos):
            await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)

    if pdfs:
        await msg.reply_text("*📄 PDF LINKS:*", parse_mode="Markdown")
        for chunk in format_content_list(pdfs):
            await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)


async def get_videos_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    if uid not in user_sessions:
        await msg.reply_text("⚠️ Please /login first.")
        return
    session = user_sessions[uid]
    await msg.reply_text("⚙️ Extracting video links...")
    items  = fetch_all_batches(session["token"], uid)
    videos = [i for i in items if "VIDEO" in i["type"]]
    await msg.reply_text(f"✅ Found *{len(videos)}* videos:", parse_mode="Markdown")
    for chunk in format_content_list(videos):
        await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)


async def get_pdfs_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    if uid not in user_sessions:
        await msg.reply_text("⚠️ Please /login first.")
        return
    session = user_sessions[uid]
    await msg.reply_text("⚙️ Extracting PDF links...")
    items = fetch_all_batches(session["token"], uid)
    pdfs  = [i for i in items if "PDF" in i["type"]]
    await msg.reply_text(f"✅ Found *{len(pdfs)}* PDFs:", parse_mode="Markdown")
    for chunk in format_content_list(pdfs):
        await msg.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)


async def show_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    info = (
        "🔍 *Bridge to Success — App Analysis*\n\n"
        "📦 *Package*: `com.lct.bmightc`\n"
        "🏗 *Platform*: learncentre.tech (StudyTrend SaaS)\n"
        "🌐 *API Base*: `study_api_sprint13_security_promo`\n\n"
        "⚠️ *Security Loopholes Found:*\n\n"
        "1️⃣ *IDOR on Storage URLs* — PDFs & videos at predictable paths:\n"
        "   `…/public/storage/pdf/<filename>` — no auth check\n\n"
        "2️⃣ *Unauthenticated Free Content* — `/get-free-video` & `/get-free-pdf` "
        "accessible without token\n\n"
        "3️⃣ *API Hardcoded in Plaintext* — full API path visible in APK DEX\n\n"
        "4️⃣ *No Certificate Pinning* — MITM proxy intercepts all traffic\n\n"
        "5️⃣ *Token in SharedPreferences* — readable on rooted device\n\n"
        "6️⃣ *Video Proxy Exposed* — `ytdl.movx.in` & `ytapi.skynetwing.com` "
        "return direct MP4/HLS without auth\n\n"
        "7️⃣ *Test URL User Impersonation* — `?test_id=X&user_id=Y` injectable\n\n"
        "8️⃣ *Security-by-obscurity* — 'sprint13_security_promo' is not real security\n\n"
        "📡 *All Media Storage Bases:*\n"
        f"`{STORAGE_VID}`\n`{STORAGE_PDF}`\n"
        f"`{PLAYER_URL}<ID>`\n`{LIVE_URL}<ID>`"
    )
    await msg.reply_text(info, parse_mode="Markdown", disable_web_page_preview=True)


async def logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in user_sessions:
        del user_sessions[uid]
    msg = (
        update.callback_query.message
        if hasattr(update, "callback_query") and update.callback_query
        else update.message
    )
    await msg.reply_text("🚪 Logged out. Session cleared.")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    if   action == "menu_login"  : await login_start(update, context)
    elif action == "menu_free"   : await get_free_content(update, context)
    elif action == "menu_batches": await get_all_batches(update, context)
    elif action == "menu_videos" : await get_videos_only(update, context)
    elif action == "menu_pdfs"   : await get_pdfs_only(update, context)
    elif action == "menu_info"   : await show_info(update, context)
    elif action == "menu_logout" : await logout(update, context)


# ─────────────────────────────────────────────────────────────────────────────
# HEALTH CHECK SERVER  (required for Koyeb Web Service — binds to $PORT)
# ─────────────────────────────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Bot is running")

    def log_message(self, format, *args):
        pass  # suppress access logs


def run_health_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health server listening on port {port}")
    server.serve_forever()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set!")
        sys.exit(1)

    # Start health-check HTTP server in a background daemon thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Build and start the Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("help",    help_cmd))
    app.add_handler(CommandHandler("login",   login_start))
    app.add_handler(CommandHandler("free",    get_free_content))
    app.add_handler(CommandHandler("batches", get_all_batches))
    app.add_handler(CommandHandler("videos",  get_videos_only))
    app.add_handler(CommandHandler("pdfs",    get_pdfs_only))
    app.add_handler(CommandHandler("info",    show_info))
    app.add_handler(CommandHandler("logout",  logout))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
