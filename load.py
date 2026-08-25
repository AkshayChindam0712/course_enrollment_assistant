import csv
import sqlite3
from pathlib import Path


DATA_DIR = Path("data")
DB_FILE = Path("enrolment.db")


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    student_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    year INTEGER,
    programme TEXT NOT NULL,
    fees_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    course_code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    term TEXT NOT NULL,
    day TEXT NOT NULL,
    start TEXT NOT NULL,
    end TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prerequisites (
    course_code TEXT NOT NULL,
    requires TEXT NOT NULL,
    minimum_grade REAL NOT NULL,

    PRIMARY KEY (course_code, requires),

    FOREIGN KEY (course_code)
        REFERENCES courses(course_code),

    FOREIGN KEY (requires)
        REFERENCES courses(course_code)
);

CREATE TABLE IF NOT EXISTS enrolments (
    student_id TEXT NOT NULL,
    course_code TEXT NOT NULL,
    status TEXT NOT NULL,
    grade REAL,

    PRIMARY KEY (student_id, course_code),

    FOREIGN KEY (student_id)
        REFERENCES students(student_id),

    FOREIGN KEY (course_code)
        REFERENCES courses(course_code)
);

CREATE TABLE IF NOT EXISTS current_numbers (
    course_code TEXT PRIMARY KEY,
    enrolled_now INTEGER NOT NULL,

    FOREIGN KEY (course_code)
        REFERENCES courses(course_code)
);
"""


def read_csv(filename):

    path = DATA_DIR / filename

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as file:

        return list(csv.DictReader(file))


def load_data():

    connection = sqlite3.connect(DB_FILE)

    connection.execute("PRAGMA foreign_keys = ON")

    try:

        # Create the five tables
        connection.executescript(SCHEMA)

        # Clear existing imported data.
        # This makes running load.py twice deterministic.
        connection.execute("DELETE FROM enrolments")
        connection.execute("DELETE FROM prerequisites")
        connection.execute("DELETE FROM current_numbers")
        connection.execute("DELETE FROM courses")
        connection.execute("DELETE FROM students")

        # --------------------------------------------------
        # STUDENTS
        # --------------------------------------------------

        students = read_csv("students.csv")

        for row in students:

            student_id = row["student_id"].strip()
            name = row["name"].strip()
            programme = row["programme"].strip()

            year_text = row["year"].strip()

            if year_text == "":
                year = None
            else:
                year = int(year_text)

            # Handle PAID / paid
            fees_status = row["fees_status"].strip().lower()

            connection.execute(
                """
                INSERT INTO students
                (
                    student_id,
                    name,
                    year,
                    programme,
                    fees_status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    name,
                    year,
                    programme,
                    fees_status
                )
            )

        # --------------------------------------------------
        # COURSES
        # --------------------------------------------------

        courses = read_csv("courses.csv")

        for row in courses:

            connection.execute(
                """
                INSERT INTO courses
                (
                    course_code,
                    title,
                    credits,
                    capacity,
                    term,
                    day,
                    start,
                    end
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["course_code"].strip(),
                    row["title"].strip(),
                    int(row["credits"]),
                    int(row["capacity"]),
                    row["term"].strip(),
                    row["day"].strip(),
                    row["start"].strip(),
                    row["end"].strip()
                )
            )

        # --------------------------------------------------
        # PREREQUISITES
        # --------------------------------------------------

        prerequisites = read_csv("prerequisites.csv")

        for row in prerequisites:

            connection.execute(
                """
                INSERT INTO prerequisites
                (
                    course_code,
                    requires,
                    minimum_grade
                )
                VALUES (?, ?, ?)
                """,
                (
                    row["course_code"].strip(),
                    row["requires"].strip(),
                    float(row["minimum_grade"])
                )
            )

        # --------------------------------------------------
        # ENROLMENTS
        # --------------------------------------------------

        enrolments = read_csv("enrolments.csv")

        for row in enrolments:

            student_id = row["student_id"].strip()
            course_code = row["course_code"].strip()
            status = row["status"].strip().lower()

            grade_text = row["grade"].strip()

            # Current enrolments do not have a grade.
            if status == "enrolled":
                grade = None

            # Completed courses must have a grade.
            elif status == "completed":

                if grade_text == "":
                    raise ValueError(
                        f"Completed course has no grade: "
                        f"{student_id} - {course_code}"
                    )

                grade = float(grade_text)

            else:

                raise ValueError(
                    f"Unknown enrolment status: {status}"
                )

            connection.execute(
                """
                INSERT INTO enrolments
                (
                    student_id,
                    course_code,
                    status,
                    grade
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    student_id,
                    course_code,
                    status,
                    grade
                )
            )

        # --------------------------------------------------
        # CURRENT NUMBERS
        # --------------------------------------------------

        current_numbers = read_csv("current_numbers.csv")

        for row in current_numbers:

            connection.execute(
                """
                INSERT INTO current_numbers
                (
                    course_code,
                    enrolled_now
                )
                VALUES (?, ?)
                """,
                (
                    row["course_code"].strip(),
                    int(row["enrolled_now"])
                )
            )

        connection.commit()

        print("Database loaded successfully.")
        print(f"Database: {DB_FILE}")

    except Exception:

        connection.rollback()
        raise

    finally:

        connection.close()


if __name__ == "__main__":
    load_data()