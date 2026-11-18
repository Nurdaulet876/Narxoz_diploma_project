import os
import hashlib
import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ANONYMIZE_PII = os.getenv("ANONYMIZE_PII", "false").lower() == "true"
HASH_SALT = os.getenv("HASH_SALT", "")
GENERATED_OUTPUT_FILE = os.getenv("GENERATED_OUTPUT_FILE", "generated_canvas_export.csv")

# Department course catalog matching realistic university course codes
COURSES_CATALOG = [
    {"course_id": 1, "course_code": "202610:CSS4004-ENG-1", "course_name": "Распределенные системы"},
    {"course_id": 2, "course_code": "202610:PSY2001-RUS-1", "course_name": "Психология личности"},
    {"course_id": 3, "course_code": "202610:CSS3012-ENG-1", "course_name": "Архитектура баз данных"},
    {"course_id": 4, "course_code": "202610:MGT2105-RUS-1", "course_name": "Управление конфликтами"},
    {"course_id": 5, "course_code": "202610:CSS4102-ENG-2", "course_name": "DevOps"},
    {"course_id": 6, "course_code": "202610:PHI1001-RUS-1", "course_name": "Философия"},
    {"course_id": 7, "course_code": "202610:DAT3008-ENG-1", "course_name": "Машинное обучение"},
    {"course_id": 8, "course_code": "202610:LAW2004-RUS-1", "course_name": "IT инфраструктура"},
    {"course_id": 9, "course_code": "202610:CSS3025-ENG-1", "course_name": "Шаблоны проектирования"},
    {"course_id": 10, "course_code": "202610:ECO2010-RUS-1", "course_name": "Цифровая экономика"},
    {"course_id": 11, "course_code": "202610:SEC4001-ENG-1", "course_name": "Информационная безопасность"},
    {"course_id": 12, "course_code": "202610:COM1005-RUS-1", "course_name": "Академическое письмо"},
]

# Exact 22-column schema produced by export_canvas_data.py
SCHEMA_COLUMNS = [
    "course_id",
    "course_code",
    "course_name",
    "course_files_count",
    "online_assignments_count",
    "due_online_assignments_count",
    "offline_assignments_count",
    "student_id",
    "student_name",
    "total_time_seconds",
    "days_since_last_activity",
    "submitted_count",
    "submission_rate",
    "late_count",
    "missing_count",
    "total_attempts",
    "student_comments",
    "avg_hours_before_deadline",
    "online_score",
    "offline_score",
    "total_score",
    "current_weighted_score",
]


def format_student_identity(raw_uid: int, raw_name: str) -> tuple[str | int, str]:
    """Optionally hash student_id and mask student_name to match ANONYMIZE_PII mode."""
    if not ANONYMIZE_PII:
        return raw_uid, raw_name
    digest = hashlib.sha256(f"{HASH_SALT}:{raw_uid}".encode()).hexdigest()[:12]
    return digest, f"Student_{digest[:6]}"


def generate_department_dataset(
    n_students: int = 220,
    students_per_course: int = 90,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate realistic multi-course Canvas LMS records calibrated to REST API export."""
    rng = np.random.default_rng(seed)

    # Create a shared student pool enrolled across multiple department courses
    students = [
        {
            "raw_id": 8 + i,
            "raw_name": f"Student {i + 1}",
            "base_habit": rng.choice(["high", "medium", "low", "ghost"], p=[0.28, 0.37, 0.22, 0.13]),
        }
        for i in range(n_students)
    ]

    rows = []

    for course in COURSES_CATALOG:
        cid = course["course_id"]

        # Vary offline/seminar grading share naturally across courses (0% to 60%)
        offline_share = float(rng.choice([0.0, 0.2, 0.4, 0.6], p=[0.4, 0.2, 0.2, 0.2]))
        online_weight = round(100.0 * (1.0 - offline_share), 1)
        offline_weight = round(100.0 - online_weight, 1)

        if offline_share == 0.0:
            course_files_count = int(rng.integers(5, 16))
            online_assignments_count = int(rng.integers(6, 10))
            offline_assignments_count = 0
        else:
            course_files_count = int(rng.integers(15, 35))
            online_assignments_count = int(rng.integers(2, 6))
            offline_assignments_count = int(rng.integers(3, 8))

        # Simulate different points in the semester (past-due online tasks)
        semester_progress = float(rng.uniform(0.35, 0.85))
        due_online_assignments_count = max(1, int(round(online_assignments_count * semester_progress)))

        # Baseline days elapsed since the latest activity in this course
        course_base_inactive = float(rng.uniform(1.5, 22.0))

        enrolled = rng.choice(students, size=min(students_per_course, n_students), replace=False)

        for st in enrolled:
            # Allow student engagement on a specific subject to diverge from baseline habit
            roll = rng.random()
            if st["base_habit"] == "ghost":
                profile = "ghost" if roll < 0.85 else "low"
            elif roll < 0.70:
                profile = st["base_habit"]
            else:
                profile = rng.choice(["high", "medium", "low"])

            # Scale expected LMS time with the course's online workload share
            workload_factor = 0.4 + 0.6 * (1.0 - offline_share)

            if profile == "high":
                time_sec = int(rng.normal(2200 * workload_factor, 400 * workload_factor))
                inactivity_lag = float(rng.uniform(0.0, 1.5))
                # Occasional early submission ahead of upcoming deadlines (submission_rate > 1.0)
                early_bonus = 1 if (due_online_assignments_count < online_assignments_count and rng.random() < 0.15) else 0
                submitted_count = due_online_assignments_count + early_bonus
                late_count = 0
                hours_early = float(rng.normal(22.0, 8.0))
                comments = int(rng.integers(0, 3))
            elif profile == "medium":
                time_sec = int(rng.normal(750 * workload_factor, 180 * workload_factor))
                inactivity_lag = float(rng.uniform(0.8, 4.0))
                submitted_count = max(1, int(round(due_online_assignments_count * rng.uniform(0.5, 1.0))))
                late_count = int(rng.integers(0, 2)) if submitted_count > 0 else 0
                hours_early = float(rng.normal(7.0, 5.0))
                comments = int(rng.integers(0, 2))
            elif profile == "low":
                time_sec = int(rng.normal(240 * workload_factor, 80 * workload_factor))
                inactivity_lag = float(rng.uniform(2.5, 9.0))
                submitted_count = int(rng.integers(0, max(1, due_online_assignments_count // 2 + 1)))
                late_count = int(rng.integers(0, submitted_count + 1))
                hours_early = float(rng.normal(-2.0, 4.5)) if submitted_count > 0 else np.nan
                comments = 0
            else:  # ghost
                time_sec = int(rng.integers(0, 120))
                inactivity_lag = float(rng.uniform(6.0, 20.0))
                submitted_count = 0
                late_count = 0
                hours_early = np.nan
                comments = 0

            # Simulate Canvas background timer quirk (~8% active students have 0s recorded)
            if profile != "ghost" and rng.random() < 0.08:
                time_sec = 0
            # Inject ~5% AFK tab-left-open time outliers
            elif time_sec > 0 and rng.random() < 0.05:
                time_sec *= int(rng.integers(5, 10))

            time_sec = max(0, time_sec)
            missing_count = max(0, due_online_assignments_count - submitted_count)
            submission_rate = round(submitted_count / due_online_assignments_count, 2)
            total_attempts = submitted_count + int(rng.integers(0, 2)) if submitted_count > 0 else 0
            days_inactive = round(course_base_inactive + inactivity_lag, 2)

            # Compute online and offline scores on a combined 0-100 scale
            capped_rate = min(1.0, submission_rate)
            if online_weight > 0:
                quality = (
                    rng.uniform(0.84, 1.0) if profile == "high"
                    else rng.uniform(0.62, 0.85) if profile == "medium"
                    else rng.uniform(0.35, 0.62)
                )
                raw_online = capped_rate * online_weight * quality - (late_count * 3.5)
                online_score = round(float(np.clip(raw_online, 0.0, online_weight)), 1)
            else:
                online_score = 0.0

            if offline_weight > 0:
                offline_eff = (
                    rng.uniform(0.82, 1.0) if profile == "high"
                    else rng.uniform(0.58, 0.84) if profile == "medium"
                    else rng.uniform(0.30, 0.56) if profile == "low"
                    else rng.uniform(0.0, 0.12)
                )
                offline_score = round(float(np.clip(offline_weight * offline_eff, 0.0, offline_weight)), 1)
            else:
                offline_score = 0.0

            total_score = round(float(np.clip(online_score + offline_score + rng.normal(0, 1.5), 0.0, 100.0)), 1)
            student_id, student_name = format_student_identity(st["raw_id"], st["raw_name"])

            rows.append({
                "course_id": cid,
                "course_code": course["course_code"],
                "course_name": course["course_name"],
                "course_files_count": course_files_count,
                "online_assignments_count": online_assignments_count,
                "due_online_assignments_count": due_online_assignments_count,
                "offline_assignments_count": offline_assignments_count,
                "student_id": student_id,
                "student_name": student_name,
                "total_time_seconds": time_sec,
                "days_since_last_activity": days_inactive,
                "submitted_count": submitted_count,
                "submission_rate": submission_rate,
                "late_count": late_count,
                "missing_count": missing_count,
                "total_attempts": total_attempts,
                "student_comments": comments,
                "avg_hours_before_deadline": round(hours_early, 1) if not np.isnan(hours_early) else None,
                "online_score": online_score,
                "offline_score": offline_score,
                "total_score": total_score,
                "current_weighted_score": total_score,
            })

    df = pd.DataFrame(rows, columns=SCHEMA_COLUMNS)
    return df


def main():
    df = generate_department_dataset(n_students=220, students_per_course=90, seed=42)
    df.to_csv(GENERATED_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"Generated {len(df)} rows across {df['course_id'].nunique()} courses -> {GENERATED_OUTPUT_FILE}")
    print(df[["course_code", "student_name", "total_time_seconds", "submission_rate", "online_score", "offline_score", "total_score"]].head(10))


if __name__ == "__main__":
    main()