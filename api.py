import json
import sqlite3
from pathlib import Path
from pydantic import BaseModel
from fastapi import Query

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse

from rules import check_all, reasons
class AskRequest(BaseModel):
    student_id: str
    message: str

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "enrolment.db"

REQUESTS_DIR = (
    BASE_DIR
    / "data"
    / "requests"
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Course Enrolment Assistant",
    description=(
        "Course enrolment checking assistant"
    ),
    version="1.0.0"
)

BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
def home():
    return FileResponse("index.html")

BASE_DIR = Path(__file__).resolve().parent


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/style.css")
def css():
    return FileResponse(BASE_DIR / "style.css", media_type="text/css")


@app.get("/script.js")
def javascript():
    return FileResponse(
        BASE_DIR / "script.js",
        media_type="application/javascript"
    )

@app.get("/")
def home():
    return FileResponse(BASE_DIR / "index.html")


@app.get("/style.css")
def style():
    return FileResponse(
        BASE_DIR / "style.css",
        media_type="text/css"
    )


@app.get("/script.js")
def script():
    return FileResponse(
        BASE_DIR / "script.js",
        media_type="application/javascript"
    )

# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException
):

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "data": None,
            "error": str(exc.detail)
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):

    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "data": None,
            "error": "Invalid request parameters"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception
):

    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "data": None,
            "error": "Internal server error"
        }
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DB_FILE
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# ============================================================
# 1. GET STUDENT
# ============================================================

@app.get(
    "/students/{student_id}"
)
def get_student(
    student_id: str
):

    connection = get_connection()

    try:

        student = connection.execute(
            """
            SELECT
                student_id,
                name,
                year,
                programme,
                fees_status

            FROM students

            WHERE student_id = ?
            """,
            (student_id,)
        ).fetchone()

        if student is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Student "
                    f"'{student_id}' not found"
                )
            )

        return {
            "ok": True,
            "data": dict(student),
            "error": None
        }

    finally:

        connection.close()


# ============================================================
# 2. GET STUDENT ENROLMENTS
# ============================================================

@app.get(
    "/students/{student_id}/enrolments"
)
def get_student_enrolments(
    student_id: str
):

    connection = get_connection()

    try:

        student = connection.execute(
            """
            SELECT student_id
            FROM students
            WHERE student_id = ?
            """,
            (student_id,)
        ).fetchone()

        if student is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Student "
                    f"'{student_id}' not found"
                )
            )

        enrolments = connection.execute(
            """
            SELECT
                e.student_id,
                e.course_code,
                c.title,
                e.status,
                e.grade

            FROM enrolments AS e

            JOIN courses AS c
                ON c.course_code = e.course_code

            WHERE e.student_id = ?

            ORDER BY e.course_code
            """,
            (student_id,)
        ).fetchall()

        return {
            "ok": True,
            "data": [
                dict(row)
                for row in enrolments
            ],
            "error": None
        }

    finally:

        connection.close()


# ============================================================
# 3. GET COURSES
# ============================================================

@app.get("/courses")
def get_courses():

    connection = get_connection()

    try:

        courses = connection.execute(
            """
            SELECT
                c.course_code,
                c.title,
                c.credits,
                c.capacity,
                c.term,
                c.day,
                c.start,
                c.end,
                n.enrolled_now,

                CASE
                    WHEN n.enrolled_now >= c.capacity
                    THEN 1
                    ELSE 0
                END AS full

            FROM courses AS c

            JOIN current_numbers AS n
                ON n.course_code = c.course_code

            ORDER BY c.course_code
            """
        ).fetchall()

        return {
            "ok": True,
            "data": [
                dict(row)
                for row in courses
            ],
            "error": None
        }

    finally:

        connection.close()


# ============================================================
# 4. GET ONE COURSE
# ============================================================

@app.get(
    "/courses/{course_code}"
)
def get_course(
    course_code: str
):

    connection = get_connection()

    try:

        course = connection.execute(
            """
            SELECT
                c.course_code,
                c.title,
                c.credits,
                c.capacity,
                c.term,
                c.day,
                c.start,
                c.end,
                n.enrolled_now

            FROM courses AS c

            JOIN current_numbers AS n
                ON n.course_code = c.course_code

            WHERE c.course_code = ?
            """,
            (course_code,)
        ).fetchone()

        if course is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Course "
                    f"'{course_code}' not found"
                )
            )

        prerequisites = connection.execute(
            """
            SELECT
                requires,
                minimum_grade

            FROM prerequisites

            WHERE course_code = ?

            ORDER BY requires
            """,
            (course_code,)
        ).fetchall()

        result = dict(course)

        result["prerequisites"] = [
            dict(row)
            for row in prerequisites
        ]

        return {
            "ok": True,
            "data": result,
            "error": None
        }

    finally:

        connection.close()


# ============================================================
# 5. CHECK COURSE DIRECTLY
# ============================================================

@app.get(
    "/check/{student_id}/{course_code}"
)
def check_enrolment(
    student_id: str,
    course_code: str
):

    connection = get_connection()

    try:

        student = connection.execute(
            """
            SELECT student_id
            FROM students
            WHERE student_id = ?
            """,
            (student_id,)
        ).fetchone()

        if student is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Student "
                    f"'{student_id}' not found"
                )
            )

        course = connection.execute(
            """
            SELECT course_code
            FROM courses
            WHERE course_code = ?
            """,
            (course_code,)
        ).fetchone()

        if course is None:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Course "
                    f"'{course_code}' not found"
                )
            )

    finally:

        connection.close()

    rule_results = check_all(
        student_id,
        course_code
    )

    blocking_reasons = reasons(
        rule_results
    )

    return {
        "ok": True,

        "data": {
            "student_id": student_id,
            "course_code": course_code,
            "eligible": (
                len(blocking_reasons) == 0
            ),
            "rules": rule_results,
            "reasons": blocking_reasons
        },

        "error": None
    }


# ============================================================
# 6. PROCESS STUDENT REQUEST
#
# This connects the complete pipeline:
#
# message
#    ↓
# extract.py
#    ↓
# course_code
#    ↓
# rules.py
#    ↓
# handbook
#    ↓
# reply.py
#    ↓
# final response
# ============================================================

@app.get(
    "/requests/{request_id}/answer"
)
def answer_request(
    request_id: str
):

    # --------------------------------------------------------
    # Read request
    # --------------------------------------------------------

    request_file = (
        REQUESTS_DIR
        / f"{request_id}.json"
    )

    if not request_file.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                f"Request "
                f"'{request_id}' not found"
            )
        )

    try:

        with open(
            request_file,
            "r",
            encoding="utf-8"
        ) as file:

            request_data = json.load(file)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Request "
                f"'{request_id}' contains "
                f"invalid JSON"
            )
        )

    student_id = request_data.get(
        "student_id"
    )

    message = request_data.get(
        "message"
    )

    if not student_id:

        raise HTTPException(
            status_code=400,
            detail="student_id is missing"
        )

    if not message:

        raise HTTPException(
            status_code=400,
            detail="message is missing"
        )

    # ========================================================
    # COURSE EXTRACTION
    # ========================================================

    try:

        from extract import (
            extract_course_code
        )

        extraction = extract_course_code(
            message
        )

    except Exception as error:

        return {
            "ok": False,

            "data": {
                "request_id": request_id,
                "student_id": student_id,
                "message": message,
                "course_code": None,
                "eligible": False,
                "reasons": [],
                "handbook": [],
                "reply": (
                    "I could not identify "
                    "the course from your message."
                )
            },

            "error": (
                f"Course extraction failed: "
                f"{error}"
            )
        }

    # --------------------------------------------------------
    # Read extraction result
    # --------------------------------------------------------

    if isinstance(
        extraction,
        dict
    ):

        course_code = extraction.get(
            "course_code"
        )

        extraction_status = extraction.get(
            "status"
        )

        extraction_error = extraction.get(
            "error"
        )

    else:

        course_code = extraction

        extraction_status = (
            "success"
            if course_code
            else "failed"
        )

        extraction_error = None

    # --------------------------------------------------------
    # Invalid extraction
    # --------------------------------------------------------

    if not course_code:

        return {
            "ok": False,

            "data": {
                "request_id": request_id,
                "student_id": student_id,
                "message": message,
                "course_code": None,
                "extraction_status":
                    extraction_status,
                "eligible": False,
                "reasons": [],
                "handbook": [],
                "reply": (
                    "I could not identify "
                    "a valid course from "
                    "your message."
                )
            },

            "error": extraction_error
        }

    # ========================================================
    # VERIFY COURSE
    # ========================================================

    connection = get_connection()

    try:

        course = connection.execute(
            """
            SELECT
                course_code,
                title

            FROM courses

            WHERE course_code = ?
            """,
            (course_code,)
        ).fetchone()

    finally:

        connection.close()

    if course is None:

        return {
            "ok": False,

            "data": {
                "request_id": request_id,
                "student_id": student_id,
                "message": message,
                "course_code": course_code,
                "eligible": False,
                "reasons": [],
                "handbook": [],
                "reply": (
                    "The identified course "
                    "does not exist."
                )
            },

            "error": (
                f"Course '{course_code}' "
                "not found"
            )
        }

    # ========================================================
    # RUN RULES
    # ========================================================

    rule_results = check_all(
        student_id,
        course_code
    )

    blocking_reasons = reasons(
        rule_results
    )

    eligible = (
        len(blocking_reasons) == 0
    )

    # ========================================================
    # HANDBOOK + AI REPLY
    # ========================================================

    handbook = []

    reply_valid = True

    if blocking_reasons:

        try:

            from reply import (
                get_handbook_for_reasons,
                generate_valid_reply,
                handbook_file_names,
                
            )

            handbook_documents = (
                get_handbook_for_reasons(
                    blocking_reasons
                )
            )

            handbook = (
                handbook_file_names(
                    handbook_documents
                )
            )

            final_reply, reply_valid = (
                generate_valid_reply(
                    student_id,
                    course_code,
                    blocking_reasons,
                    handbook_documents
                )
            )


        except Exception as error:

            print(
                "AI reply error:",
                error
            )

            final_reply = (
                "Enrolment is blocked because: "
                + "; ".join(
                    blocking_reasons
                )
                + "."
            )

            reply_valid = False

    else:

        final_reply = (
            f"You are eligible to enrol "
            f"in {course_code}."
        )

    # ========================================================
    # FINAL API RESPONSE
    # ========================================================

    return {

        "ok": True,

        "data": {

            "request_id": request_id,

            "student_id": student_id,

            "message": message,

            "course_code": course_code,

            "course_title": course["title"],

            "eligible": eligible,

            "rules": rule_results,

            "reasons": blocking_reasons,

            "handbook": handbook,

            "reply": final_reply,

            "reply_valid": reply_valid
        },

        "error": None
    }


# ============================================================
# 7. GET RAW REQUEST
# ============================================================

@app.get(
    "/requests/{request_id}"
)
def get_request(
    request_id: str
):

    request_file = (
        REQUESTS_DIR
        / f"{request_id}.json"
    )

    if not request_file.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                f"Request "
                f"'{request_id}' not found"
            )
        )

    try:

        with open(
            request_file,
            "r",
            encoding="utf-8"
        ) as file:

            request_data = json.load(file)

    except json.JSONDecodeError:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Request "
                f"'{request_id}' contains "
                f"invalid JSON"
            )
        )

    return {
        "ok": True,
        "data": request_data,
        "error": None
    }
    # ============================================================
# ASK FROM WEBPAGE
# ============================================================
@app.get("/ask")
def ask_question(
    student_id: str = Query(..., description="Student ID, e.g. S-102"),
    message: str = Query(..., description="Natural-language enrolment question")
):

    student_id = student_id.strip().upper()
    message = message.strip()

    print()
    print("=" * 60)
    print("ASK REQUEST RECEIVED")
    print("=" * 60)
    print("Student:", student_id)
    print("Message:", message)

    if not student_id:
        raise HTTPException(
            status_code=400,
            detail="Student ID is required"
        )

    if not message:
        raise HTTPException(
            status_code=400,
            detail="Question is required"
        )

    # --------------------------------------------------------
    # Verify student
    # --------------------------------------------------------

    connection = get_connection()

    try:
        student = connection.execute(
            """
            SELECT
                student_id,
                name,
                year,
                programme,
                fees_status
            FROM students
            WHERE student_id = ?
            """,
            (student_id,)
        ).fetchone()
    finally:
        connection.close()

    if student is None:
        raise HTTPException(
            status_code=404,
            detail=f"Student '{student_id}' not found"
        )

    # --------------------------------------------------------
    # TASK 8 - EXTRACT COURSE
    # --------------------------------------------------------

    print("Extracting course...")

    try:
        from extract import extract_course_code

        extraction = extract_course_code(message)

        if isinstance(extraction, dict):
            course_code = extraction.get("course_code")
        else:
            course_code = extraction

        if course_code:
            course_code = str(course_code).strip().upper()

    except Exception as error:
        print("Extraction error:", error)

        return {
            "ok": False,
            "student_id": student_id,
            "message": message,
            "course_code": None,
            "reply": "I could not identify the course from your question.",
            "error": str(error)
        }

    print("Extracted course:", course_code)

    if not course_code:
        return {
            "ok": False,
            "student_id": student_id,
            "message": message,
            "course_code": None,
            "reply": "I could not identify a valid course from your question.",
            "error": "Course extraction failed"
        }

    # --------------------------------------------------------
    # GET COURSE
    # --------------------------------------------------------

    connection = get_connection()

    try:
        course = connection.execute(
            """
            SELECT
                course_code,
                title
            FROM courses
            WHERE course_code = ?
            """,
            (course_code,)
        ).fetchone()
    finally:
        connection.close()

    if course is None:
        return {
            "ok": False,
            "student_id": student_id,
            "message": message,
            "course_code": course_code,
            "course_title": None,
            "reply": f"Course {course_code} was not found.",
            "error": f"Course '{course_code}' not found"
        }

    # --------------------------------------------------------
    # RUN ALL FIVE RULES
    # --------------------------------------------------------

    print("Running enrolment rules...")

    rule_results = check_all(
        student_id,
        course_code
    )

    blocking_reasons = reasons(
        rule_results
    )

    eligible = len(blocking_reasons) == 0

    print("Reasons:", blocking_reasons)

    # --------------------------------------------------------
    # TASK 9 - AI REPLY
    # --------------------------------------------------------

    handbook = []
    reply_valid = True

    if blocking_reasons:



        try:
            from reply import (
                get_handbook_for_reasons,
                generate_valid_reply,
                handbook_file_names,
                validate_reply
            )

            handbook_documents = get_handbook_for_reasons(
                blocking_reasons
            )

            handbook = handbook_file_names(
                handbook_documents
            )

            ai_reply = generate_valid_reply(
                student_id,
                course_code,
                blocking_reasons,
                handbook_documents
            ) 

            print("Reply valid:", reply_valid)

            final_reply = ai_reply

        except Exception as error:

            print("AI reply error:", error)

            final_reply = (
                "Enrolment is blocked because: "
                + "; ".join(blocking_reasons)
                + "."
            )

            reply_valid = False

    else:

        print("Student is eligible.")

        final_reply = (
            f"You are eligible to enrol in {course_code}."
        )

    print("=" * 60)
    print("FINAL AI RESPONSE")
    print(final_reply)
    print("=" * 60)

    return {
        "ok": True,
        "student_id": student_id,
        "message": message,
        "course_code": course_code,
        "course_title": course["title"],
        "eligible": eligible,
        "rules": rule_results,
        "reasons": blocking_reasons,
        "handbook": handbook,
        "reply": final_reply,
        "reply_valid": reply_valid,
        "error": None
    }

    # --------------------------------------------------------
    # RESPONSE TO STREAMLIT
    # --------------------------------------------------------

    return {
        "ok": True,
        "data": {
            "student_id": student_id,
            "message": message,
            "course_code": course_code,
            "course_title": course["title"],
            "eligible": eligible,
            "rules": rule_results,
            "reasons": blocking_reasons,
            "handbook": handbook,
            "reply": ai_reply,
            "reply_valid": reply_valid
        },
        "error": None
    }