import json
import re
import sqlite3
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from rules import check_all, reasons


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "enrolment.db"
REQUESTS_DIR = BASE_DIR / "data" / "requests"
HANDBOOK_DIR = BASE_DIR / "data" / "handbook"

MODEL_NAME = "HuggingFaceTB/SmolLM2-1.7B-Instruct"


# ============================================================
# LOAD MODEL ONCE
# ============================================================

print("Loading AI reply model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    dtype=torch.float16
)

model.eval()

print("Model loaded.")



# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DB_FILE
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# GET HANDBOOK TEXT
# ============================================================

def get_handbook_text(
    handbook_files
):

    documents = []

    for filename in handbook_files:

        path = HANDBOOK_DIR / filename

        if not path.exists():
            continue

        text = path.read_text(
            encoding="utf-8"
        ).strip()

        if text:

            documents.append(
                {
                    "file": filename,
                    "text": text
                }
            )

    return documents


# ============================================================
# FIND RELEVANT HANDBOOK PAGES
# ============================================================

def get_handbook_for_reasons(
    blocking_reasons
):

    files = []

    reason_text = " ".join(
        str(reason)
        for reason in blocking_reasons
        if reason is not None
    ).lower()

    # --------------------------------------------------------
    # Fees
    # --------------------------------------------------------

    if "fees" in reason_text:

        files.append(
            "fees.md"
        )

    # --------------------------------------------------------
    # Credit limit
    # --------------------------------------------------------

    if (
        "credit" in reason_text
        or "60" in reason_text
    ):

        files.append(
            "credit_limit.md"
        )

    # --------------------------------------------------------
    # Prerequisite
    # --------------------------------------------------------

    if (
        "grade" in reason_text
        or "prerequisite" in reason_text
        or "needs" in reason_text
    ):

        files.append(
            "prerequisites.md"
        )

        # Task 9: advice can be relevant when
        # prerequisite is missing.
        files.append(
            "advice.md"
        )

        # Task 9: waiver information may be needed
        # for prerequisite problems.
        files.append(
            "waivers.md"
        )

    # --------------------------------------------------------
    # Capacity
    # --------------------------------------------------------

    if (
        "full" in reason_text
        or "capacity" in reason_text
    ):

        files.append(
            "capacity.md"
        )

        files.append(
            "advice.md"
        )

    # --------------------------------------------------------
    # Timetable
    # --------------------------------------------------------

    if (
        "clash" in reason_text
        or "timetable" in reason_text
    ):

        files.append(
            "timetable.md"
        )

    # --------------------------------------------------------
    # Waiver explicitly mentioned
    # --------------------------------------------------------

    if (
        "waiver" in reason_text
        or "waive" in reason_text
    ):

        files.append(
            "waivers.md"
        )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    files = list(
        dict.fromkeys(files)
    )

    return get_handbook_text(
        files
    )


# ============================================================
# GET HANDBOOK FILE NAMES
# ============================================================

def handbook_file_names(
    handbook_documents
):

    return [
        document["file"]
        for document in handbook_documents
    ]


# ============================================================
# BUILD HANDBOOK TEXT
# ============================================================

def build_handbook_text(
    handbook_documents
):

    sections = []

    for document in handbook_documents:

        sections.append(
            f"--- {document['file']} ---\n"
            f"{document['text']}"
        )

    return "\n\n".join(
        sections
    )


# ============================================================
# EXTRACT COURSE CODES
# ============================================================

def extract_course_codes(
    text
):

    if not text:
        return []

    return re.findall(
        r"\b[A-Z]{2,4}\d{3}\b",
        text.upper()
    )


# ============================================================
# EXTRACT NUMBERS
# ============================================================

def extract_numbers(
    text
):

    if not text:
        return []

    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        text
    )


# ============================================================
# BUILD AI PROMPT
# ============================================================

def build_prompt(
    student_id,
    course_code,
    blocking_reasons,
    handbook_documents
):

    reasons_text = "\n".join(
        f"REASON {i}: {reason}"
        for i, reason in enumerate(
            blocking_reasons,
            start=1
        )
    )

    handbook_text = build_handbook_text(
        handbook_documents
    )

    # --------------------------------------------------------
    # IMPORTANT:
    # Hide prerequisite/other course codes from the model.
    # Keep only the target course code.
    # --------------------------------------------------------

    all_text = (
        reasons_text
        + "\n"
        + handbook_text
    )

    found_codes = extract_course_codes(
        all_text
    )

    for code in found_codes:

        if code.upper() != course_code.upper():

            reasons_text = reasons_text.replace(
                code,
                "the earlier course"
            )

            handbook_text = handbook_text.replace(
                code,
                "the earlier course"
            )

    return f"""
You are a college course-enrolment assistant.

TARGET COURSE: {course_code}
STUDENT ID: {student_id}

BLOCKING REASONS:
{reasons_text}

HANDBOOK:
{handbook_text}

Write ONLY a short 2-3 sentence student-facing reply.

Rules:
1. Use {course_code} as the target course.
2. Never confuse the earlier/prerequisite course with the target course.
3. Explain every blocking reasons.
4. Explain why enrolment is blocked.
5. Give the next action from the handbook.
6. Mention the relevant handbook filename.
7. Use the student ID exactly as provided.
8. Use only supplied facts.
9. if there are multiple blocking reasons, explain EVERY reason in the reply.
10. Do not invent course codes.
11. Do not say the enrolment is approved.
12. If waiver information is provided and waiver is relevant,
    mention who approves the waiver.
13. Return only the final student-facing reply.
Return only 2-3 sentences.
""".strip()


# ============================================================
# GENERATE AI REPLY
# ============================================================

def generate_reply(
    student_id,
    course_code,
    blocking_reasons,
    handbook_documents
):

    prompt = build_prompt(
        student_id,
        course_code,
        blocking_reasons,
        handbook_documents
    )

    messages = [
        {
            "role": "user",
            "content": prompt
        }
    ]

    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt"
    )

    # --------------------------------------------------------
    # Handle BatchEncoding or Tensor
    # --------------------------------------------------------

    if hasattr(
        inputs,
        "input_ids"
    ):

        input_ids = inputs.input_ids

        attention_mask = (
            inputs.attention_mask
        )

    # --------------------------------------------------------
    # Generate
    # --------------------------------------------------------

    with torch.no_grad():

        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=60,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = output[
        0
    ][
        input_ids.shape[-1]:
    ]

    reply = tokenizer.decode(
        generated,
        skip_special_tokens=True
    ).strip()

    return reply


# ============================================================
# VALIDATE REPLY
# ============================================================

def validate_reply(
    reply,
    student_id,
    course_code,
    blocking_reasons,
    handbook_documents
):

    # --------------------------------------------------------
    # 1. Reply must exist
    # --------------------------------------------------------

    if not isinstance(
        reply,
        str
    ):
        print(
            "Validation failed: reply is not text"
        )
        return False

    reply = reply.strip()

    if not reply:
        print(
            "Validation failed: empty reply"
        )
        return False

    reply_lower = reply.lower()

    # --------------------------------------------------------
    # 2. Every blocking reason must be addressed
    # --------------------------------------------------------

    ignored_words = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "been",
        "needs",
        "need",
        "must",
        "student",
        "course",
        "enrolment",
        "enrollment",
        "because"
    }

    for reason in blocking_reasons:

        words = []

        for word in reason.lower().split():

            cleaned = word.strip(
                ".,:;()[]"
            )

            if (
                len(cleaned) >= 4
                and cleaned not in ignored_words
            ):

                words.append(
                    cleaned
                )

        if words:

            matched = any(
                word in reply_lower
                for word in words
            )

            if not matched:

                print(
                    "Validation failed: "
                    "reason not addressed:",
                    reason
                )

                return False

    # --------------------------------------------------------
    # 3. Correct target course code
    # --------------------------------------------------------

    reply_codes = set(
        extract_course_codes(
            reply
        )
    )

    if course_code.upper() not in reply_codes:

        print(
            "Validation failed: "
            "target course code missing"
        )

        print(
            "Expected:",
            course_code
        )

        print(
            "Found:",
            reply_codes
        )

        return False

    # No other course code allowed
    extra_codes = (
        reply_codes
        - {course_code.upper()}
    )

    if extra_codes:

        print(
            "Validation failed: "
            "wrong/invented course code"
        )

        print(
            "Expected:",
            course_code
        )

        print(
            "Found:",
            extra_codes
        )

        return False

    # --------------------------------------------------------
    # 4. Build supplied text
    # --------------------------------------------------------

    supplied_text = " ".join(
        str(reason)
        for reason in blocking_reasons
        if reason is not None
    )

    for document in handbook_documents:

        supplied_text += " "

        supplied_text += str(
            document.get("text") or ""
        )

    # --------------------------------------------------------
    # 5. Number validation
    # --------------------------------------------------------

    supplied_numbers = set(
        extract_numbers(
            supplied_text
        )
    )

    reply_numbers = set(
        extract_numbers(
            reply
        )
    )

    # --------------------------------------------------------
    # Allow numeric part of student ID
    # Example: S-104 -> 104
    # --------------------------------------------------------

    if student_id:

        student_id_number = "".join(
            char
            for char in str(student_id)
            if char.isdigit()
        )

        if student_id_number:

            reply_numbers.discard(
                student_id_number
            )

    # --------------------------------------------------------
    # Allow numeric part of target course code
    # Example: CS301 -> 301
    # --------------------------------------------------------

    course_digits = "".join(
        char
        for char in str(course_code)
        if char.isdigit()
    )

    if course_digits:

        reply_numbers.discard(
            course_digits
        )

    unknown_numbers = (
        reply_numbers
        - supplied_numbers
    )

    if unknown_numbers:

        print(
            "Validation failed: "
            "unsupported number:",
            unknown_numbers
        )

        print(
            "Allowed numbers:",
            supplied_numbers
        )

        return False

    # --------------------------------------------------------
    # 6. Student ID validation
    # --------------------------------------------------------

    if student_id:

        if str(student_id).lower() not in reply_lower:

            print(
                "Validation failed: "
                "student ID missing"
            )

            return False

    

    # --------------------------------------------------------
    # 8. Waiver validation
    # --------------------------------------------------------

    if "waiver" in reply_lower:

        waiver_text = ""

        for document in handbook_documents:

            if (
                str(document.get("file", "")).lower()
                == "waivers.md"
            ):

                waiver_text += str(
                    document.get("text") or ""
                ).lower()

        if not waiver_text:

            print(
                "Validation failed: "
                "waiver mentioned but waivers.md "
                "was not provided"
            )

            return False

        # No approval claim
        forbidden_approval_phrases = [
            "enrolment approved",
            "enrollment approved",
            "enrolment is approved",
            "enrollment is approved",
            "successfully enrolled",
            "enrolment successful",
            "enrollment successful"
        ]

        if any(
            phrase in reply_lower
            for phrase in forbidden_approval_phrases
        ):

            print(
                "Validation failed: "
                "enrolment approval mentioned"
            )

            return False

        # ----------------------------------------------------
        # Check that waiver approver information exists
        # in the supplied waiver handbook.
        # ----------------------------------------------------

        approver_words = [
            "approve",
            "approves",
            "approval",
            "department",
            "coordinator",
            "registrar",
            "dean"
        ]

        if not any(
            word in waiver_text
            for word in approver_words
        ):

            print(
                "Validation warning: "
                "waiver approver not found in handbook"
            )

    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    print(
        "Validation passed"
    )

    return True


# ============================================================
# FALLBACK
# ============================================================

def plain_reasons(
    blocking_reasons
):

    return (
        "Enrolment is blocked because: "
        + "; ".join(
            str(reason)
            for reason in blocking_reasons
        )
        + "."
    )


# ============================================================
# GENERATE + VALIDATE + RETRY ONCE
# ============================================================

def generate_valid_reply(
    student_id,
    course_code,
    blocking_reasons,
    handbook_documents
):

    # --------------------------------------------------------
    # FIRST ATTEMPT
    # --------------------------------------------------------

    print(
        "Generating first AI reply..."
    )

    reply_1 = generate_reply(
        student_id,
        course_code,
        blocking_reasons,
        handbook_documents
    )

    print(
        "Validating first AI reply..."
    )

    valid_1 = validate_reply(
        reply_1,
        student_id,
        course_code,
        blocking_reasons,
        handbook_documents
    )

    if valid_1:

        print(
            "First reply validation passed."
        )

        return reply_1, True

    # --------------------------------------------------------
    # SECOND ATTEMPT
    # --------------------------------------------------------

    print(
        "First reply validation failed."
    )

    print(
        "Generating second AI reply..."
    )

    reply_2 = generate_reply(
        student_id,
        course_code,
        blocking_reasons,
        handbook_documents
    )

    print(
        "Validating second AI reply..."
    )

    valid_2 = validate_reply(
        reply_2,
        student_id,
        course_code,
        blocking_reasons,
        handbook_documents
    )

    if valid_2:

        print(
            "Second reply validation passed."
        )

        return reply_2, True

    # --------------------------------------------------------
    # BOTH FAILED
    # --------------------------------------------------------

    print(
        "Second reply validation failed."
    )

    print(
        "Returning plain blocking reasons."
    )

    return (
        plain_reasons(
            blocking_reasons
        ),
        False,
    )


# ============================================================
# PROCESS ONE REQUEST
# ============================================================

def process_request(
    request_id
):

    request_file = (
        REQUESTS_DIR
        / f"{request_id}.json"
    )

    if not request_file.exists():

        return {
            "request_id": request_id,
            "error": "Request file not found",
            "course_code": None,
            "reasons": [],
            "handbook": [],
            "reply": None,
            "reply_valid": False
        }

    # --------------------------------------------------------
    # Load request
    # --------------------------------------------------------

    with open(
        request_file,
        "r",
        encoding="utf-8"
    ) as file:

        request_data = json.load(
            file
        )

    student_id = request_data.get(
        "student_id"
    )

    message = request_data.get(
        "message"
    )

    if not student_id:

        return {
            "request_id": request_id,
            "error": "student_id missing",
            "course_code": None,
            "reasons": [],
            "handbook": [],
            "reply": None,
            "reply_valid": False
        }

    if not message:

        return {
            "request_id": request_id,
            "error": "message missing",
            "course_code": None,
            "reasons": [],
            "handbook": [],
            "reply": None,
            "reply_valid": False
        }

    # --------------------------------------------------------
    # TASK 8: Extract course
    # --------------------------------------------------------

    from extract import extract_course_code

    extraction = extract_course_code(
        message
    )

    if isinstance(
        extraction,
        dict
    ):

        course_code = extraction.get(
            "course_code"
        )

    else:

        course_code = extraction

    if course_code:

        course_code = str(
            course_code
        ).strip().upper()

    if not course_code:

        return {
            "request_id": request_id,
            "student_id": student_id,
            "message": message,
            "course_code": None,
            "reasons": [],
            "handbook": [],
            "reply": (
                "I could not identify "
                "the course from your message."
            ),
            "reply_valid": False
        }

    print(
        "Extracted course:",
        course_code
    )

    # --------------------------------------------------------
    # Verify course exists
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
            "request_id": request_id,
            "student_id": student_id,
            "message": message,
            "course_code": course_code,
            "reasons": [],
            "handbook": [],
            "reply": (
                f"Course {course_code} "
                "was not found."
            ),
            "reply_valid": False
        }

    # --------------------------------------------------------
    # RUN RULES
    # --------------------------------------------------------

    rule_result = check_all(
        student_id,
        course_code
    )

    blocking_reasons = reasons(
        rule_result
    )

    # --------------------------------------------------------
    # HANDBOOK
    # --------------------------------------------------------

    handbook_documents = (
        get_handbook_for_reasons(
            blocking_reasons
        )
    )

    handbook_files = handbook_file_names(
        handbook_documents
    )

    # --------------------------------------------------------
    # AI REPLY
    # --------------------------------------------------------

    if blocking_reasons:

        reply, reply_valid = (
            generate_valid_reply(
                student_id,
                course_code,
                blocking_reasons,
                handbook_documents
            )
        )

    else:

        reply = (
            f"{student_id}, you are eligible "
            f"to enrol in {course_code}."
        )

        reply_valid = True

    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {
        "request_id": request_id,
        "student_id": student_id,
        "message": message,
        "course_code": course_code,
        "eligible": len(
            blocking_reasons
        ) == 0,
        "rules": rule_result,
        "reasons": blocking_reasons,
        "handbook": handbook_files,
        "reply": reply,
        "reply_valid": reply_valid
    }


# ============================================================
# PROCESS ALL SIX REQUESTS
# ============================================================

def process_all_requests():

    request_ids = [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6"
    ]

    results = []

    for request_id in request_ids:

        print()
        print("=" * 60)
        print(
            f"Request: {request_id}"
        )
        print("=" * 60)

        try:

            result = process_request(
                request_id
            )

        except Exception as error:

            print(
                "ERROR:",
                repr(error)
            )

            result = {
                "request_id": request_id,
                "error": str(error),
                "course_code": None,
                "reasons": None,
                "handbook": None,
                "reply": None,
                "reply_valid": False
            }

        results.append(
            result
        )

        print()
        print(
            "Course:",
            result.get(
                "course_code"
            )
        )

        print(
            "Reasons:",
            result.get(
                "reasons"
            )
        )

        print(
            "Handbook:",
            result.get(
                "handbook"
            )
        )

        print()
        print(
            "FINAL REPLY"
        )

        print(
            result.get(
                "reply"
            )
        )

        print(
            "Reply valid:",
            result.get(
                "reply_valid"
            )
        )

    return results


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    results
):

    output_file = (
        BASE_DIR
        / "task9_results.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            results,
            file,
            indent=2
        )

    print()
    print(
        f"Saved results to: {output_file}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(
        "Processing all requests..."
    )
    print("=" * 60)

    results = process_all_requests()

    save_results(
        results
    )

    print()
    print("=" * 60)
    print(
        "PROCESSING COMPLETE"
    )
    print("=" * 60)

    for result in results:

        print(
            f"{result.get('request_id')} -> "
            f"{result.get('course_code')} -> "
            f"{result.get('reply_valid')}"
        )