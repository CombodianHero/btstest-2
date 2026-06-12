"""
Bridge to Success — No-Login Batch Extractor
==============================================
Extracts all available course/batch info WITHOUT any login.

How this works (confirmed from APK reverse engineering):
  - Every request adds two headers from AppManager.getT():
      ktx  = "com.lct.bmightc"   (app package name)
      ktxx = "12.0"               (app version key)
  - AppManager.getUserId() returns "" (empty string) when not logged in
  - allCourses / topCourses / getCategory all accept userId=""
  - The server trusts the ktx/ktxx headers to identify the app

API Base: https://bridgetosuccess.learncentre.tech/public/study_api_sprint13_security_promo/
Package : com.lct.bmightc

What this script extracts (no login needed):
  - All available courses/batches (name, ID, price, image, category)
  - Top/featured courses
  - Subject/category list inside each course
  - Free videos & PDFs (publicly listed)
  - Course info (description, faculty, duration)

What requires login:
  - Enrolled course videos (myCourseVideo)
  - Enrolled course PDFs  (myCoursePdf)
  - Live class links

Usage:
    pip install requests
    python bridgetosuccess_nologin_extractor.py
"""

import sys, os, re, time, json
import requests

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ─── Constants ────────────────────────────────────────────────────────────────
API_BASE    = "https://bridgetosuccess.learncentre.tech/public/study_api_sprint13_security_promo/"
COURSE_HOST = "https://bridgetosuccess.learncentre.tech/public/storage/course/"
VIDEO_HOST  = "https://bridgetosuccess.learncentre.tech/public/storage/video/"
PDF_HOST    = "https://bridgetosuccess.learncentre.tech/public/storage/pdf/"

# Injected on every request by AppManager.getT() — confirmed from smali
APP_HEADERS = {
    "ktx":  "com.lct.bmightc",   # package name
    "ktxx": "12.0",               # version key
}

HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Accept":       "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer":      "https://bridgetosuccess.learncentre.tech/",
    "Origin":       "https://bridgetosuccess.learncentre.tech",
    **APP_HEADERS,
}

# ─── Colors ───────────────────────────────────────────────────────────────────
class C:
    HEADER = '\033[95m'
    BLUE   = '\033[94m'
    CYAN   = '\033[96m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    RED    = '\033[91m'
    BOLD   = '\033[1m'
    END    = '\033[0m'

# ─── Core API Call ────────────────────────────────────────────────────────────
def post(tag: str, extra: dict = {}) -> dict | None:
    """POST to the API. userId="" works for all public endpoints."""
    payload = {"tag": tag, "userId": "", **extra}
    try:
        r = requests.post(API_BASE, data=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.Timeout:
        print(f"{C.RED}  [!] Timeout on tag={tag}{C.END}")
    except requests.exceptions.HTTPError as e:
        print(f"{C.RED}  [!] HTTP {e.response.status_code} on tag={tag}{C.END}")
    except Exception as e:
        print(f"{C.RED}  [!] Error on tag={tag}: {e}{C.END}")
    return None


def safe_list(data, *keys) -> list:
    """Extract a list from nested dict keys, trying each key."""
    if not data:
        return []
    for k in keys:
        val = data.get(k)
        if isinstance(val, list) and val:
            return val
    return []


def sanitize(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return re.sub(r'[\s_]+', '_', name).strip('_. ') or "Unknown"


# ─── Banner ───────────────────────────────────────────────────────────────────
def print_banner():
    print(f"""
{C.CYAN}{C.BOLD}
╔══════════════════════════════════════════════════════════════════╗
║     Bridge to Success  —  No-Login Batch Extractor              ║
║     ──────────────────────────────────────────────              ║
║     Extracts ALL courses & free content without login           ║
╚══════════════════════════════════════════════════════════════════╝
{C.END}""")


# ─── Fetch Functions ──────────────────────────────────────────────────────────
def fetch_all_courses() -> list:
    """tag: allCourses | userId: "" | isEBook: 0"""
    print(f"{C.YELLOW}[*] Fetching all courses...{C.END}")
    data = post("allCourses", {"isEBook": "0"})
    return safe_list(data, "data", "courses", "course")


def fetch_top_courses() -> list:
    """tag: topCourses | userId: "" | isEBook: 0"""
    print(f"{C.YELLOW}[*] Fetching top/featured courses...{C.END}")
    data = post("topCourses", {"isEBook": "0"})
    return safe_list(data, "data", "courses", "course")


def fetch_course_info(course_id: str) -> dict:
    """tag: courseInfo | courseId, userId: ""  — description, faculty, etc."""
    data = post("courseInfo", {"courseId": course_id})
    if data:
        return data.get("data") or {}
    return {}


def fetch_subjects(course_id: str) -> list:
    """tag: getCategory | courseId, categoryId: ""  — subject list"""
    data = post("getCategory", {"courseId": course_id, "categoryId": ""})
    result = safe_list(data, "data", "categories", "category", "subjects")
    if not result:
        # fallback: getAllCategory
        data2 = post("getAllCategory", {"courseId": course_id})
        result = safe_list(data2, "data", "categories", "category")
    return result


def fetch_free_videos(user_id: str = "") -> list:
    """tag: freeCourseVideo | userId: ""  — publicly listed free videos"""
    data = post("freeCourseVideo", {"userId": user_id})
    return safe_list(data, "data", "videos", "video")


def fetch_free_pdfs(user_id: str = "") -> list:
    """tag: freeCoursePdf | userId: ""  — publicly listed free PDFs"""
    data = post("freeCoursePdf", {"userId": user_id})
    return safe_list(data, "data", "pdfs", "pdf")


def fetch_configuration() -> dict:
    """tag: configuration  — app settings, player config"""
    data = post("configuration")
    return data or {}


def fetch_banners() -> list:
    """tag: banner | userId: "", bannerType: ""  — home banners"""
    data = post("banner", {"bannerType": ""})
    return safe_list(data, "data", "banners", "banner")


# ─── Display ──────────────────────────────────────────────────────────────────
def get_field(obj: dict, *keys):
    """Try multiple keys, return first non-empty value."""
    for k in keys:
        v = obj.get(k)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def display_courses(courses: list, label: str = "COURSES"):
    if not courses:
        print(f"{C.RED}  No courses found.{C.END}")
        return

    print(f"\n{C.GREEN}{C.BOLD}{'═'*78}")
    print(f"  {label}  ({len(courses)} found)")
    print(f"{'═'*78}{C.END}")
    print(f"{C.BOLD}  {'#':<4} {'TITLE':<42} {'ID':<10} {'PRICE':<10} {'FREE'}{C.END}")
    print(f"{C.GREEN}  {'─'*74}{C.END}")

    for i, c in enumerate(courses, 1):
        title = get_field(c, "title", "courseName", "name", "course_name")[:40]
        cid   = get_field(c, "id", "courseId", "course_id")[:8]
        price = get_field(c, "price", "coursePrice", "amount", "fee") or "N/A"
        free  = "YES" if str(c.get("isFree", c.get("free", "0"))) in ("1", "true", "True") else "no"

        col = C.CYAN if i % 2 == 0 else C.BLUE
        print(f"{col}  {i:<4} {title:<42} {cid:<10} {price:<10} {free}{C.END}")

    print(f"{C.GREEN}{'═'*78}{C.END}\n")


# ─── Extraction ───────────────────────────────────────────────────────────────
def extract_single_course(course: dict, outfile, depth: int = 0) -> tuple[int, int, int]:
    """
    Extract subjects + free videos/PDFs for one course.
    Returns (videos, pdfs, subjects).
    """
    pad = "  " * depth

    course_id    = get_field(course, "id", "courseId", "course_id")
    course_title = get_field(course, "title", "courseName", "name") or f"Course_{course_id}"
    course_img   = get_field(course, "courseImage", "image", "thumbnail", "thumb")
    course_price = get_field(course, "price", "coursePrice", "amount") or "N/A"
    course_desc  = get_field(course, "description", "courseDescription", "about") or ""
    faculty      = get_field(course, "facultyName", "faculty", "teacher", "instructor") or ""
    is_free      = str(course.get("isFree", course.get("free", "0"))) in ("1", "true", "True")

    outfile.write(f"{pad}┌{'─'*74}┐\n")
    outfile.write(f"{pad}│  COURSE  : {course_title}\n")
    outfile.write(f"{pad}│  ID      : {course_id}\n")
    outfile.write(f"{pad}│  Price   : {'FREE' if is_free else course_price}\n")
    if faculty:
        outfile.write(f"{pad}│  Faculty : {faculty}\n")
    if course_img:
        img_url = COURSE_HOST + course_img if not course_img.startswith("http") else course_img
        outfile.write(f"{pad}│  Image   : {img_url}\n")
    if course_desc:
        outfile.write(f"{pad}│  About   : {course_desc[:200]}\n")
    outfile.write(f"{pad}└{'─'*74}┘\n\n")

    total_videos = 0
    total_pdfs   = 0

    if not course_id:
        outfile.write(f"{pad}  [!] No course ID — cannot fetch subjects.\n\n")
        return 0, 0, 0

    # ── Fetch Subjects ──
    subjects = fetch_subjects(course_id)
    outfile.write(f"{pad}  Subjects found: {len(subjects)}\n\n")
    time.sleep(0.3)

    for s_idx, subj in enumerate(subjects, 1):
        sub_id   = get_field(subj, "id", "categoryId", "subjectId", "subject_id")
        sub_name = get_field(subj, "categoryName", "name", "subjectName", "title") or f"Subject {s_idx}"
        sub_count = get_field(subj, "classCount", "videoCount", "count") or ""

        outfile.write(f"{pad}  {'─'*70}\n")
        outfile.write(f"{pad}  ► SUBJECT [{s_idx}]: {sub_name}\n")
        outfile.write(f"{pad}    ID: {sub_id}")
        if sub_count:
            outfile.write(f"  |  Items: {sub_count}")
        outfile.write("\n\n")

        # Free videos under this subject
        sub_videos = []
        sub_pdfs   = []

        # Try myCourseVideo with empty userId - returns content list
        vdata = post("myCourseVideo", {"categoryId": sub_id, "userId": ""})
        sub_videos = safe_list(vdata, "data", "videos", "video")

        pdata = post("myCoursePdf", {"categoryId": sub_id, "userId": ""})
        sub_pdfs = safe_list(pdata, "data", "pdfs", "pdf")

        if sub_videos:
            outfile.write(f"{pad}    ── VIDEOS ({len(sub_videos)}) ──\n")
            for v in sub_videos:
                v_title = get_field(v, "title", "videoTitle", "name") or "Untitled"
                v_id    = get_field(v, "id", "videoId")
                v_link  = get_field(v, "videoLink", "link", "url", "streamUrl")
                v_file  = get_field(v, "videoFile", "file", "fileName")
                v_ytid  = get_field(v, "ytvideoId", "youtubeId", "yt_id")
                v_type  = get_field(v, "videoType", "type", "playerType")
                v_dur   = get_field(v, "duration", "videoDuration")
                v_lock  = get_field(v, "isLock", "locked", "isPurchased")

                outfile.write(f"{pad}    • {v_title}\n")
                outfile.write(f"{pad}      ID    : {v_id}  |  Type: {v_type}  |  Duration: {v_dur or 'N/A'}\n")
                outfile.write(f"{pad}      Locked: {v_lock or 'N/A'}\n")

                if v_link:
                    outfile.write(f"{pad}      Link  : {v_link}\n")
                if v_file:
                    full = VIDEO_HOST + v_file if not v_file.startswith("http") else v_file
                    outfile.write(f"{pad}      File  : {full}\n")
                if v_ytid:
                    outfile.write(f"{pad}      YT    : https://www.youtube.com/watch?v={v_ytid}\n")
                outfile.write("\n")
                total_videos += 1
        else:
            outfile.write(f"{pad}    (No videos or access required)\n")

        if sub_pdfs:
            outfile.write(f"\n{pad}    ── PDFs ({len(sub_pdfs)}) ──\n")
            for p in sub_pdfs:
                p_title = get_field(p, "title", "pdfTitle", "name") or "Untitled"
                p_id    = get_field(p, "id", "pdfId")
                p_file  = get_field(p, "pdfFile", "file", "url", "fileName")
                p_lock  = get_field(p, "isLock", "locked", "isPurchased")

                outfile.write(f"{pad}    • {p_title}\n")
                outfile.write(f"{pad}      ID    : {p_id}  |  Locked: {p_lock or 'N/A'}\n")
                if p_file:
                    full = PDF_HOST + p_file if not p_file.startswith("http") else p_file
                    outfile.write(f"{pad}      PDF   : {full}\n")
                outfile.write("\n")
                total_pdfs += 1
        else:
            outfile.write(f"{pad}    (No PDFs or access required)\n")

        outfile.write("\n")
        time.sleep(0.35)

    return total_videos, total_pdfs, len(subjects)


def extract_free_section(outfile):
    """Extract globally listed free videos and PDFs."""
    print(f"\n{C.CYAN}[*] Fetching free videos & PDFs...{C.END}")

    free_videos = fetch_free_videos()
    free_pdfs   = fetch_free_pdfs()

    outfile.write(f"\n{'═'*80}\n")
    outfile.write(f"  FREE VIDEOS & PDFs (No Login Required)\n")
    outfile.write(f"{'═'*80}\n\n")

    if free_videos:
        outfile.write(f"── FREE VIDEOS ({len(free_videos)}) ──\n\n")
        for v in free_videos:
            v_title = get_field(v, "title", "videoTitle", "name") or "Untitled"
            v_link  = get_field(v, "videoLink", "link", "url")
            v_file  = get_field(v, "videoFile", "file")
            v_ytid  = get_field(v, "ytvideoId", "youtubeId")
            v_type  = get_field(v, "videoType", "type") or "N/A"
            outfile.write(f"  • {v_title}  [type: {v_type}]\n")
            if v_link:  outfile.write(f"    Link : {v_link}\n")
            if v_file:  outfile.write(f"    File : {VIDEO_HOST + v_file}\n")
            if v_ytid:  outfile.write(f"    YT   : https://www.youtube.com/watch?v={v_ytid}\n")
            outfile.write("\n")
    else:
        outfile.write("  (No free videos found)\n\n")

    if free_pdfs:
        outfile.write(f"── FREE PDFs ({len(free_pdfs)}) ──\n\n")
        for p in free_pdfs:
            p_title = get_field(p, "title", "pdfTitle", "name") or "Untitled"
            p_file  = get_field(p, "pdfFile", "file", "url")
            outfile.write(f"  • {p_title}\n")
            if p_file:  outfile.write(f"    PDF  : {PDF_HOST + p_file}\n")
            outfile.write("\n")
    else:
        outfile.write("  (No free PDFs found)\n\n")

    print(f"{C.GREEN}  Free videos: {len(free_videos)}  |  Free PDFs: {len(free_pdfs)}{C.END}")
    return len(free_videos), len(free_pdfs)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    print_banner()

    # ── Step 1: Fetch all courses ──
    all_courses = fetch_all_courses()
    top_courses = fetch_top_courses()

    if not all_courses and not top_courses:
        print(f"{C.RED}[!] Could not fetch any courses.")
        print(f"    Possible reasons:")
        print(f"    1. API endpoint changed (check if sprint13 is still active)")
        print(f"    2. Server requires login even for allCourses")
        print(f"    3. Network issue{C.END}")
        sys.exit(1)

    # Merge and deduplicate
    seen = set()
    combined = []
    for c in (all_courses + top_courses):
        cid = c.get("id") or c.get("courseId") or id(c)
        if cid not in seen:
            seen.add(cid)
            combined.append(c)

    print(f"{C.GREEN}[+] Found {len(combined)} course(s) total{C.END}")

    # ── Step 2: Display ──
    display_courses(combined, "ALL AVAILABLE BATCHES / COURSES")

    # ── Step 3: User choice ──
    print(f"{C.BOLD}What would you like to do?{C.END}")
    print(f"  1. Extract ALL courses at once (full dump)")
    print(f"  2. Extract a specific course")
    print(f"  3. Extract only free videos & PDFs")
    print(f"  4. Show all course info (no deep extraction)")

    choice = input(f"\n{C.YELLOW}Select (1/2/3/4): {C.END}").strip()

    output_dir = os.path.dirname(os.path.abspath(__file__))

    # ── Option 3: Free content only ──
    if choice == "3":
        fname = "BridgeToSuccess_Free_Content.txt"
        fpath = os.path.join(output_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("BRIDGE TO SUCCESS — FREE CONTENT\n")
            f.write(f"Extracted: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            extract_free_section(f)
        print(f"\n{C.GREEN}[+] Saved to: {fpath}{C.END}")
        return

    # ── Option 4: Info only ──
    if choice == "4":
        fname = "BridgeToSuccess_CourseList.txt"
        fpath = os.path.join(output_dir, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("BRIDGE TO SUCCESS — COURSE LIST\n")
            f.write(f"Extracted: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total Courses: {len(combined)}\n\n")
            f.write(f"{'─'*80}\n\n")
            for i, c in enumerate(combined, 1):
                title    = get_field(c, "title", "courseName", "name") or "N/A"
                cid      = get_field(c, "id", "courseId") or "N/A"
                price    = get_field(c, "price", "coursePrice", "amount") or "N/A"
                faculty  = get_field(c, "facultyName", "faculty", "teacher") or "N/A"
                img      = get_field(c, "courseImage", "image", "thumbnail") or ""
                is_free  = str(c.get("isFree", c.get("free", "0"))) in ("1","true","True")
                desc     = get_field(c, "description", "courseDescription", "about") or ""
                f.write(f"[{i}] {title}\n")
                f.write(f"    ID      : {cid}\n")
                f.write(f"    Price   : {'FREE' if is_free else price}\n")
                f.write(f"    Faculty : {faculty}\n")
                if img:
                    f.write(f"    Image   : {COURSE_HOST + img if not img.startswith('http') else img}\n")
                if desc:
                    f.write(f"    About   : {desc[:300]}\n")
                f.write("\n")
        print(f"\n{C.GREEN}[+] Saved to: {fpath}{C.END}")
        return

    # ── Options 1 & 2: Deep extraction ──
    if choice == "1":
        targets = combined
        fname = "BridgeToSuccess_ALL_Courses.txt"
    elif choice == "2":
        while True:
            try:
                idx = int(input(f"{C.YELLOW}Enter course number (1-{len(combined)}): {C.END}")) - 1
                if 0 <= idx < len(combined):
                    targets = [combined[idx]]
                    title_slug = sanitize(get_field(combined[idx], "title", "courseName", "name") or "course")
                    fname = f"BridgeToSuccess_{title_slug}.txt"
                    break
                print(f"{C.RED}  Out of range.{C.END}")
            except ValueError:
                print(f"{C.RED}  Please enter a number.{C.END}")
    else:
        print(f"{C.RED}Invalid choice.{C.END}")
        return

    fpath = os.path.join(output_dir, fname)

    total_v = total_p = total_s = 0

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(f"{'='*80}\n")
        f.write(f"  BRIDGE TO SUCCESS — BATCH EXTRACTION\n")
        f.write(f"  Extracted : {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Courses   : {len(targets)}\n")
        f.write(f"{'='*80}\n\n")

        # Free content section
        fv, fp = extract_free_section(f)

        f.write(f"\n{'='*80}\n")
        f.write(f"  COURSE DETAILS\n")
        f.write(f"{'='*80}\n\n")

        for i, course in enumerate(targets, 1):
            title = get_field(course, "title", "courseName", "name") or f"Course {i}"
            print(f"\n{C.CYAN}{C.BOLD}  [{i}/{len(targets)}] Extracting: {title}{C.END}")

            v, p, s = extract_single_course(course, f)
            total_v += v
            total_p += p
            total_s += s

            print(f"{C.GREEN}      Subjects: {s}  |  Videos: {v}  |  PDFs: {p}{C.END}")

        # Summary
        f.write(f"\n{'='*80}\n")
        f.write(f"  SUMMARY\n")
        f.write(f"{'='*80}\n")
        f.write(f"  Courses extracted : {len(targets)}\n")
        f.write(f"  Total Subjects    : {total_s}\n")
        f.write(f"  Total Videos      : {total_v}\n")
        f.write(f"  Total PDFs        : {total_p}\n")
        f.write(f"  Free Videos       : {fv}\n")
        f.write(f"  Free PDFs         : {fp}\n")
        f.write(f"  Grand Total Links : {total_v + total_p + fv + fp}\n")
        f.write(f"{'='*80}\n")

    print(f"\n{C.GREEN}{C.BOLD}")
    print(f"  ╔══════════════════════════════════════════╗")
    print(f"  ║   EXTRACTION COMPLETE                    ║")
    print(f"  ╠══════════════════════════════════════════╣")
    print(f"  ║  File     : {fname:<30}║")
    print(f"  ║  Courses  : {len(targets):<30}║")
    print(f"  ║  Subjects : {total_s:<30}║")
    print(f"  ║  Videos   : {total_v:<30}║")
    print(f"  ║  PDFs     : {total_p:<30}║")
    print(f"  ╚══════════════════════════════════════════╝")
    print(f"{C.END}")
    print(f"  Saved to: {fpath}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{C.CYAN}Interrupted. Goodbye!{C.END}")
        sys.exit(0)
