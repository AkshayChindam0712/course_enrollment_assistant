import sqlite3


DB_FILE = "enrolment.db"


def get_connection():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


# ============================================================
# RULE 1 — FEES
# ============================================================

def fees_block(student_id):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT fees_status
            FROM students
            WHERE student_id = ?
            """,
            (student_id,)
        ).fetchone()

        if row is None:
            return "student not found"

        if row["fees_status"].lower() != "paid":
            return "fees are unpaid"

        return None

    finally:
        connection.close()


# ============================================================
# RULE 2 — PREREQUISITES
# ============================================================

def prerequisite_block(student_id, course):

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                p.requires,
                p.minimum_grade,
                e.status,
                e.grade

            FROM prerequisites AS p

            LEFT JOIN enrolments AS e
                ON e.course_code = p.requires
                AND e.student_id = ?

            WHERE p.course_code = ?

            ORDER BY p.requires
            """,
            (student_id, course)
        ).fetchall()

        for row in rows:

            # The prerequisite is satisfied only when:
            #
            # 1. The student completed it
            # 2. The student has a grade
            # 3. The grade is high enough

            if (
                row["status"] != "completed"
                or row["grade"] is None
                or row["grade"] < row["minimum_grade"]
            ):

                if row["grade"] is None:

                    return (
                        f"{row['requires']} grade missing, "
                        f"needs {row['minimum_grade']:g}"
                    )

                return (
                    f"{row['requires']} grade "
                    f"{row['grade']:g}, "
                    f"needs {row['minimum_grade']:g}"
                )

        return None

    finally:
        connection.close()


# ============================================================
# RULE 3 — CAPACITY
# ============================================================

def capacity_block(course):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                c.capacity,
                n.enrolled_now

            FROM courses AS c

            JOIN current_numbers AS n
                ON n.course_code = c.course_code

            WHERE c.course_code = ?
            """,
            (course,)
        ).fetchone()

        if row is None:
            return "course not found"

        if row["enrolled_now"] >= row["capacity"]:

            return (
                f"full, "
                f"{row['enrolled_now']} of "
                f"{row['capacity']}"
            )

        return None

    finally:
        connection.close()


# ============================================================
# RULE 4 — TIMETABLE CLASH
# ============================================================

def clash_block(student_id, course):

    connection = get_connection()

    try:

        # First obtain the course the student wants.
        target = connection.execute(
            """
            SELECT
                day,
                start,
                end

            FROM courses

            WHERE course_code = ?
            """,
            (course,)
        ).fetchone()

        if target is None:
            return "course not found"

        # SQL performs the join and identifies the student's
        # current courses on the same day.
        rows = connection.execute(
            """
            SELECT
                c.course_code,
                c.day,
                c.start,
                c.end

            FROM enrolments AS e

            JOIN courses AS c
                ON c.course_code = e.course_code

            WHERE e.student_id = ?
              AND e.status = 'enrolled'
              AND c.day = ?
            """,
            (
                student_id,
                target["day"]
            )
        ).fetchall()

        target_start = target["start"]
        target_end = target["end"]

        def to_minutes(value):
            hour, minute = map(int, value.split(":"))
            return hour * 60 + minute

        target_start = to_minutes(target_start)
        target_end = to_minutes(target_end)

        for row in rows:

            existing_start = to_minutes(row["start"])
            existing_end = to_minutes(row["end"])

            # Courses overlap when:
            #
            # new_start < existing_end
            # AND
            # existing_start < new_end

            if (
                target_start < existing_end
                and existing_start < target_end
            ):

                return (
                    f"clashes with "
                    f"{row['course_code']} "
                    f"{row['day']} "
                    f"{row['start']}"
                )

        return None

    finally:
        connection.close()


# ============================================================
# RULE 5 — CREDIT LIMIT
# ============================================================

def credit_block(student_id, course):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT

                COALESCE(
                    SUM(
                        CASE
                            WHEN e.status = 'enrolled'
                            THEN c.credits
                            ELSE 0
                        END
                    ),
                    0
                ) AS current_credits,

                (
                    SELECT credits
                    FROM courses
                    WHERE course_code = ?
                ) AS requested_credits

            FROM enrolments AS e

            JOIN courses AS c
                ON c.course_code = e.course_code

            WHERE e.student_id = ?
            """,
            (
                course,
                student_id
            )
        ).fetchone()

        if row is None or row["requested_credits"] is None:
            return "course not found"

        total_credits = (
            row["current_credits"]
            + row["requested_credits"]
        )

        if total_credits > 60:

            return (
                f"would be {total_credits:g} credits, "
                f"limit 60"
            )

        return None

    finally:
        connection.close()


# ============================================================
# RUN ALL FIVE RULES
# ============================================================

def check_all(student_id, course):

    return {
        "fees": fees_block(student_id),

        "prerequisite":
            prerequisite_block(student_id, course),

        "capacity":
            capacity_block(course),

        "clash":
            clash_block(student_id, course),

        "credit_limit":
            credit_block(student_id, course)
    }


def reasons(result):

    return [
        reason
        for reason in result.values()
        if reason is not None
    ]


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    tests = [
        ("S-104", "CS201"),
        ("S-101", "CS310"),
        ("S-103", "CS202"),
        ("S-102", "CS301"),
        ("S-105", "CS301"),
        ("S-106", "DS220")
    ]

    for student_id, course in tests:

        result = check_all(student_id, course)

        print()
        print(
            f"{student_id} -> {course}"
        )

        print(result)

        print(
            "Reasons:",
            reasons(result)
        )