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
        blocking_reasons
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

    if "clash" in reason_text:

        files.append(
            "timetable.md"
        )

    # --------------------------------------------------------
    # Waiver
    # --------------------------------------------------------

    if (
        "waiver" in reason_text
        or "waive" in reason_text
    ):

        files.append(
            "waivers.md"
        )

    # Remove duplicates

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
# BUILD AI PROMPT
# ============================================================

def build_prompt(
    blocking_reasons,
    handbook_documents
):

    reasons_text = "\n".join(
        f"- {reason}"
        for reason in blocking_reasons
    )

    handbook_text = build_handbook_text(
        handbook_documents
    )

    return f"""
Write a short message to the student about
why their course enrolment is blocked.

Use ONLY the information provided below.

REASONS FOUND BY THE ENROLMENT RULES:

{reasons_text}

HANDBOOK TEXT:

{handbook_text}

Requirements:

1. Every reason listed above must appear in
   the reply.

2. Explain why each reason blocks enrolment.

3. Explain what the handbook says the student
   should do next.

4. Name the handbook page when using its advice.

5. Do not invent numbers.

6. Do not invent course codes.

7. Do not invent student information.

8. Do not say the enrolment is approved.

9. Keep the reply short and suitable for a student.

Return only the student-facing message.
"""


# ============================================================
# GENERATE AI REPLY
# ============================================================

def generate_reply(
    blocking_reasons,
    handbook_documents
):

    prompt = build_prompt(
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

    if hasattr(
        inputs,
        "input_ids"
    ):

        input_ids = inputs.input_ids

        attention_mask = (
            inputs.attention_mask
        )

    else:

        input_ids = inputs

        attention_mask = torch.ones_like(
            input_ids
        )

    with torch.no_grad():

        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=180,
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
# EXTRACT NUMBERS FROM TEXT
# ============================================================

def extract_numbers(
    text
):

    return re.findall(
        r"\b\d+(?:\.\d+)?\b",
        text
    )


# ============================================================
# EXTRACT COURSE CODES
# ============================================================

def extract_course_codes(
    text
):

    return re.findall(
        r"\b[A-Z]{2,4}\d{3}\b",
        text.upper()
    )


# ============================================================
# VALIDATE REPLY
# ============================================================

def validate_reply(
    reply,
    blocking_reasons,
    handbook_documents
):

    if not reply:

        return False

    reply_lower = reply.lower()

    # --------------------------------------------------------
    # 1. Every reason must appear
    # --------------------------------------------------------

    for reason in blocking_reasons:

        if reason.lower() not in reply_lower:

            return False

    # --------------------------------------------------------
    # 2. Every number in reply must have been provided
    # --------------------------------------------------------

    supplied_text = " ".join(
        blocking_reasons
    )

    for document in handbook_documents:

        supplied_text += " "
        supplied_text += document["text"]

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

    if not reply_numbers.issubset(
        supplied_numbers
    ):

        return False

    # --------------------------------------------------------
    # 3. Every course code must have been provided
    # --------------------------------------------------------

    supplied_codes = set(
        extract_course_codes(
            supplied_text
        )
    )

    reply_codes = set(
        extract_course_codes(
            reply
        )
    )

    if not reply_codes.issubset(
        supplied_codes
    ):

        return False

    # --------------------------------------------------------
    # 4. If waiver is mentioned, handbook must be present
    # --------------------------------------------------------

    if "waiver" in reply_lower:

        waiver_present = any(
            document["file"].lower()
            == "waivers.md"
            for document in handbook_documents
        )

        if not waiver_present:

            return False

        # Never approve enrolment

        if (
            "approved" in reply_lower
            or "enrolment approved" in reply_lower
        ):

            return False

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
            blocking_reasons
        )
        + "."
    )


# ============================================================
# GENERATE WITH RETRY
# ============================================================

def generate_valid_reply(
    blocking_reasons,
    handbook_documents
):

    print(
        "Generating AI reply..."
    )

    reply = generate_reply(
        blocking_reasons,
        handbook_documents
    )

    print(
        "Validating AI reply..."
    )

    if validate_reply(
        reply,
        blocking_reasons,
        handbook_documents
    ):
        print(
            "AI reply passed validation."
        )
    else:
        print(
            "AI reply failed validation."
        )
        print(
            "Returning AI reply despite validation failure."
        )

    # Always return the AI-generated response. Validation is retained
    # for logging/diagnostics, but it no longer replaces the AI reply
    # with the plain fallback or triggers a second generation.
    return reply


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
            "error": "Request file not found"
        }

    with open(
        request_file,
        "r",
        encoding="utf-8"
    ) as file:

        request_data = json.load(
            file
        )

    student_id = request_data[
        "student_id"
    ]

    message = request_data[
        "message"
    ]

    # ========================================================
    # TASK 8
    #
    # Extract course code.
    #
    # This assumes extract.py provides:
    #
    # extract_course_code(message)
    #
    # ========================================================

    from extract import extract_course_code

    extraction = extract_course_code(
        message
    )

    # Your Task 8 function may return a dictionary

    if isinstance(
        extraction,
        dict
    ):

        course_code = extraction.get(
            "course_code"
        )

    else:

        course_code = extraction

    if not course_code:

        return {
            "request_id": request_id,
            "student_id": student_id,
            "message": message,
            "course_code": None,
            "reasons": [],
            "handbook": [],
            "reply": (
                "I could not identify the course "
                "from your message."
            ),
            "reply_valid": False
        }

    # ========================================================
    # RULES
    # ========================================================

    rule_result = check_all(
        student_id,
        course_code
    )

    blocking_reasons = reasons(
        rule_result
    )

    # ========================================================
    # HANDBOOK
    # ========================================================

    handbook_documents = (
        get_handbook_for_reasons(
            blocking_reasons
        )
    )

    handbook_files = handbook_file_names(
        handbook_documents
    )

    # ========================================================
    # AI REPLY
    # ========================================================

    if blocking_reasons:

        reply = generate_valid_reply(
            blocking_reasons,
            handbook_documents
        )

        reply_valid = validate_reply(
            reply,
            blocking_reasons,
            handbook_documents
        )

    else:

        reply = (
            "You are eligible to enrol in "
            f"{course_code}."
        )

        reply_valid = True

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

            result = {
                "request_id": request_id,
                "error": str(error)
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
    print("processing all requests...")
    print("=" * 60)

    results = process_all_requests()

    save_results(
        results
    )

    print()
    print("=" * 60)
    print("processing COMPLETE")
    print("=" * 60)

    for result in results:

        print(
            f"{result.get('request_id')} -> "
            f"{result.get('course_code')} -> "
            f"{result.get('reply_valid')}"
        )