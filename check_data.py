import csv
from pathlib import Path


DATA_DIR = Path("data")


def read_csv(filename):
    path = DATA_DIR / filename

    with open(path, "r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def check_empty_fields(data, filename):
    problems = []

    for row_number, row in enumerate(data, start=2):
        for column, value in row.items():
            if value is None or value.strip() == "":
                problems.append(
                    f"{filename}: empty value in '{column}' at row {row_number}"
                )

    return problems


def check_case_inconsistency(data, filename, columns):
    problems = []

    for column in columns:
        values = {}

        for row in data:
            value = row[column].strip()

            if value:
                values.setdefault(value.lower(), set()).add(value)

        for normalised, variants in values.items():
            if len(variants) > 1:
                problems.append(
                    f"{filename}: inconsistent values for '{column}': "
                    f"{sorted(variants)}"
                )

    return problems


def main():
    students = read_csv("students.csv")
    courses = read_csv("courses.csv")
    prerequisites = read_csv("prerequisites.csv")
    enrolments = read_csv("enrolments.csv")
    current_numbers = read_csv("current_numbers.csv")

    problems = []

    # ---------------------------------------------------------
    # 1. Empty fields
    # ---------------------------------------------------------

    required_columns = {
        "students.csv": students,
        "courses.csv": courses,
        "prerequisites.csv": prerequisites,
        "enrolments.csv": enrolments,
        "current_numbers.csv": current_numbers,
    }

    for filename, data in required_columns.items():
        problems.extend(check_empty_fields(data, filename))

    # ---------------------------------------------------------
    # 2. Inconsistent values
    # ---------------------------------------------------------

    problems.extend(
        check_case_inconsistency(
            students,
            "students.csv",
            ["fees_status"]
        )
    )

    # ---------------------------------------------------------
    # 3. Check IDs and course codes
    # ---------------------------------------------------------

    student_ids = {
        row["student_id"].strip()
        for row in students
    }

    course_codes = {
        row["course_code"].strip()
        for row in courses
    }

    for row_number, row in enumerate(enrolments, start=2):

        student_id = row["student_id"].strip()
        course_code = row["course_code"].strip()

        if student_id not in student_ids:
            problems.append(
                f"enrolments.csv: unknown student_id "
                f"'{student_id}' at row {row_number}"
            )

        if course_code not in course_codes:
            problems.append(
                f"enrolments.csv: unknown course_code "
                f"'{course_code}' at row {row_number}"
            )

    # ---------------------------------------------------------
    # 4. Completed courses must have grades
    # ---------------------------------------------------------

    # 5. Currently enrolled courses must NOT have grades
    # ---------------------------------------------------------

    for row_number, row in enumerate(enrolments, start=2):

        status = row["status"].strip().lower()
        grade = row["grade"].strip()

        if status == "completed" and grade == "":
            problems.append(
                f"enrolments.csv: completed course has no grade "
                f"at row {row_number}"
            )

        if status == "enrolled" and grade != "":
            problems.append(
                f"enrolments.csv: currently enrolled course has a grade "
                f"at row {row_number}"
            )

    # ---------------------------------------------------------
    # Print report
    # ---------------------------------------------------------

    print()
    print("=" * 60)
    print("COURSE ENROLMENT DATA QUALITY REPORT")
    print("=" * 60)

    if not problems:
        print("No data quality problems found.")
    else:
        print(f"Found {len(problems)} problem(s):")
        print()

        for problem in problems:
            print("-", problem)

    print()
    print("=" * 60)
    print("HANDLING DECISIONS")
    print("=" * 60)

    print("""
1. Empty required values:
   The loader will reject invalid required records instead of
   silently creating incomplete database rows.

2. Different capitalisation:
   Values such as 'paid' and 'PAID' will be normalised before
   rule checking. The original CSV files will not be modified.

3. Unknown student IDs or course codes:
   These records will not be loaded as valid foreign-key rows.

4. Completed courses:
   A completed course must have a grade because prerequisites
   depend on the completed grade.

5. Currently enrolled courses:
   They must not have a grade because a current enrolment does
   not satisfy a prerequisite.

The source CSV files are never modified by check_data.py.
""")


if __name__ == "__main__":
    main()