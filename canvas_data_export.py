import os
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "").rstrip("/")
TOKEN = os.getenv("TOKEN", "")
SUB_ACCOUNT_ID = os.getenv("SUB_ACCOUNT_ID", "1")
TERM_ID = os.getenv("TERM_ID", "").strip()
ANONYMIZE_PII = os.getenv("ANONYMIZE_PII", "false").lower() == "true"
HASH_SALT = os.getenv("HASH_SALT", "")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "canvas_api_export.csv")

NOW_UTC = datetime.now(timezone.utc)
OFFLINE_TYPES = {"none", "on_paper", "not_graded"}


@dataclass
class StudentStats:
    """Holds aggregated submission metrics and scores for one student in a course."""
    submitted_count: int = 0
    late_count: int = 0
    missing_count: int = 0
    total_attempts: int = 0
    student_comments: int = 0
    hours_before_deadline: list[float] = field(default_factory=list)
    online_score: float = 0.0
    offline_score: float = 0.0
    total_score: float = 0.0

    @property
    def avg_hours_early(self) -> float | None:
        if not self.hours_before_deadline:
            return None
        avg = sum(self.hours_before_deadline) / len(self.hours_before_deadline)
        return round(avg, 1)


def create_session() -> requests.Session:
    """Create an authorized HTTP session for Canvas REST API."""
    if not BASE_URL or not TOKEN:
        raise ValueError("BASE_URL and TOKEN must be set in .env")
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {TOKEN}"})
    return session


def parse_iso(dt_str: str | None) -> datetime | None:
    """Convert ISO 8601 string from Canvas API into a UTC datetime object."""
    if not dt_str:
        return None
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def is_offline_assignment(assignment: dict) -> bool:
    """Check whether an assignment is graded offline without online file/text upload."""
    sub_types = set(assignment.get("submission_types", []))
    return sub_types.issubset(OFFLINE_TYPES)


def format_student_identity(uid: int, raw_name: str) -> tuple[str | int, str]:
    """Return raw student ID/name or salted SHA-256 hashes if ANONYMIZE_PII is enabled."""
    if not ANONYMIZE_PII:
        return uid, raw_name
    digest = hashlib.sha256(f"{HASH_SALT}:{uid}".encode()).hexdigest()[:12]
    return digest, f"Student_{digest[:6]}"


def fetch_all_pages(session: requests.Session, url: str, params: dict = None) -> list:
    """Fetch all paginated items from a Canvas API endpoint."""
    items = []
    while url:
        response = session.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)

        url = response.links.get("next", {}).get("url")
        params = None  # Query params are already included in the 'next' link
    return items


def get_department_courses(session: requests.Session) -> list[dict]:
    """Fetch all published courses with active students in the configured department."""
    params = {"published": True, "with_enrollments": True, "per_page": 100}
    if TERM_ID:
        params["enrollment_term_id"] = TERM_ID

    url = f"{BASE_URL}/api/v1/accounts/{SUB_ACCOUNT_ID}/courses"
    return fetch_all_pages(session, url, params)


def summarize_assignments(assignments: list[dict]) -> tuple[dict[int, dict], int, int, int]:
    """Filter published assignments and count online, due-online, and offline tasks."""
    published = {}
    online_count = 0
    due_online_count = 0
    offline_count = 0

    for item in assignments:
        if not item.get("published"):
            continue

        published[item["id"]] = item

        if is_offline_assignment(item):
            offline_count += 1
        else:
            online_count += 1
            due_dt = parse_iso(item.get("due_at"))
            if due_dt and due_dt <= NOW_UTC:
                due_online_count += 1

    return published, online_count, due_online_count, offline_count


def collect_student_stats(submissions: list[dict], published_assignments: dict[int, dict]) -> dict[int, StudentStats]:
    """Aggregate submissions, deadline timing, and scores per student ID."""
    stats_map: dict[int, StudentStats] = {}

    for sub in submissions:
        assignment = published_assignments.get(sub.get("assignment_id"))
        if not assignment:
            continue

        uid = sub["user_id"]
        if uid not in stats_map:
            stats_map[uid] = StudentStats()
        st = stats_map[uid]

        offline = is_offline_assignment(assignment)
        sub_dt = parse_iso(sub.get("submitted_at"))
        due_dt = parse_iso(assignment.get("due_at"))

        # 1. Submission timing and deadline discipline
        if sub_dt:
            st.submitted_count += 1
            st.total_attempts += sub.get("attempt") or 1

            if due_dt:
                hours_early = (due_dt - sub_dt).total_seconds() / 3600.0
                st.hours_before_deadline.append(hours_early)

            if sub.get("late") or (due_dt and sub_dt > due_dt):
                st.late_count += 1
        elif not offline:
            if sub.get("missing") or (due_dt and NOW_UTC > due_dt):
                st.missing_count += 1

        # 2. Student-authored comments
        for comment in sub.get("submission_comments") or []:
            if comment.get("author_id") == uid:
                st.student_comments += 1

        # 3. Online vs. offline scores
        if sub.get("score") is not None:
            score = float(sub["score"])
            st.total_score += score
            if offline:
                st.offline_score += score
            else:
                st.online_score += score

    return stats_map


def build_student_row(course: dict, enrollment: dict, stats: StudentStats, files_count: int, online_cnt: int, due_online_cnt: int, offline_cnt: int,) -> dict:
    """Assemble a single flat CSV row for a student-course pair."""
    raw_uid = enrollment["user_id"]
    user = enrollment.get("user") or {}
    grades = enrollment.get("grades") or {}

    raw_name = user.get("sortable_name", f"Student {raw_uid}")
    student_id, student_name = format_student_identity(raw_uid, raw_name)

    last_act = parse_iso(enrollment.get("last_activity_at"))
    days_inactive = round((NOW_UTC - last_act).total_seconds() / 86400.0, 2) if last_act else None

    expected_tasks = due_online_cnt or online_cnt
    sub_rate = round(stats.submitted_count / expected_tasks, 2) if expected_tasks > 0 else 0.0

    return {
        "course_id": course["id"],
        "course_code": course.get("course_code", str(course["id"])),
        "course_name": course.get("name", f"Course {course['id']}"),
        "course_files_count": files_count,
        "online_assignments_count": online_cnt,
        "due_online_assignments_count": due_online_cnt,
        "offline_assignments_count": offline_cnt,
        "student_id": student_id,
        "student_name": student_name,
        "total_time_seconds": enrollment.get("total_activity_time") or 0,
        "days_since_last_activity": days_inactive,
        "submitted_count": stats.submitted_count,
        "submission_rate": sub_rate,
        "late_count": stats.late_count,
        "missing_count": stats.missing_count,
        "total_attempts": stats.total_attempts,
        "student_comments": stats.student_comments,
        "avg_hours_before_deadline": stats.avg_hours_early,
        "online_score": stats.online_score,
        "offline_score": stats.offline_score,
        "total_score": stats.total_score,
        "current_weighted_score": grades.get("current_score") or 0.0,
    }


def export_course(session: requests.Session, course: dict) -> list[dict]:
    """Fetch course data from Canvas API and return feature rows for all active students."""
    cid = course["id"]

    enrollments = fetch_all_pages(
        session,
        f"{BASE_URL}/api/v1/courses/{cid}/enrollments",
        {"type[]": "StudentEnrollment", "state[]": "active", "per_page": 100},
    )
    if not enrollments:
        return []

    try:
        files = fetch_all_pages(session, f"{BASE_URL}/api/v1/courses/{cid}/files", {"per_page": 100})
        files_count = len(files)
    except requests.HTTPError:
        files_count = 0

    assignments = fetch_all_pages(
        session,
        f"{BASE_URL}/api/v1/courses/{cid}/assignments",
        {"per_page": 100, "override_assignment_dates": True},
    )
    published, online_cnt, due_online_cnt, offline_cnt = summarize_assignments(assignments)

    submissions = fetch_all_pages(
        session,
        f"{BASE_URL}/api/v1/courses/{cid}/students/submissions",
        {"student_ids[]": "all", "include[]": "submission_comments", "per_page": 100},
    )
    stats_by_user = collect_student_stats(submissions, published)

    rows = []
    for enr in enrollments:
        uid = enr["user_id"]
        student_stats = stats_by_user.get(uid, StudentStats())
        row = build_student_row(course, enr, student_stats, files_count, online_cnt, due_online_cnt, offline_cnt)
        rows.append(row)

    return rows


def main():
    session = create_session()
    courses = get_department_courses(session)
    all_rows = []

    for course in courses:
        try:
            all_rows.extend(export_course(session, course))
        except requests.HTTPError as err:
            print(f"Skipping course {course.get('id')} due to API error: {err}")

    df = pd.DataFrame(all_rows)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Exported {len(df)} rows across {len(courses)} courses to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()