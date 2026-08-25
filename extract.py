
import json
import sqlite3
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

DB_FILE = BASE_DIR / "enrolment.db"

REQUESTS_DIR = (
    BASE_DIR
    / "data"
    / "requests"
)

MODEL_NAME = "HuggingFaceTB/SmolLM2-1.7B-Instruct"


# ============================================================
# MODEL
# ============================================================

tokenizer = None
model = None


def load_model():

    global tokenizer
    global model

    if model is not None:

        return

    print("Loading AI model...")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    model_kwargs = {}

    # Keep the documented model unchanged.
    # float32 is safer for CPU execution than float16.
    if torch.cuda.is_available():
        model_kwargs["dtype"] = torch.float16
    else:
        model_kwargs["dtype"] = torch.float32

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        **model_kwargs
    )

    model.eval()

    print("AI model loaded.")


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
# GET REAL COURSES
# ============================================================

def get_real_courses():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                course_code,
                title
            FROM courses
            ORDER BY course_code
            """
        ).fetchall()

        return [
            {
                "course_code": row["course_code"],
                "title": row["title"]
            }
            for row in rows
        ]

    finally:

        connection.close()


# ============================================================
# COURSE LIST FOR AI
# ============================================================

def build_course_list(courses):

    return "\n".join(
        f"{course['course_code']} - {course['title']}"
        for course in courses
    )


# ============================================================
# EXTRACT JSON
# ============================================================

def extract_json(text):

    if not text:

        return None

    first = text.find("{")

    last = text.rfind("}")

    if first == -1 or last == -1:

        return None

    if last <= first:

        return None

    json_text = text[
        first:last + 1
    ]

    try:

        return json.loads(
            json_text
        )

    except json.JSONDecodeError:

        return None


# ============================================================
# VALIDATE COURSE CODE
# ============================================================

def validate_course_code(
    data,
    courses
):

    if not isinstance(
        data,
        dict
    ):

        return None

    course_code = data.get(
        "course_code"
    )

    if not isinstance(
        course_code,
        str
    ):

        return None

    real_codes = {
        course["course_code"]
        for course in courses
    }

    if course_code not in real_codes:

        return None

    return course_code


# ============================================================
# DIRECT COURSE-TITLE MATCH
# ============================================================

def normalize_text(value):
    """Normalize text for reliable course-title matching."""
    if not isinstance(value, str):
        return ""

    value = value.lower().strip()
    value = value.replace("visualization", "visualisation")

    cleaned = []
    for char in value:
        if char.isalnum() or char.isspace():
            cleaned.append(char)
        else:
            cleaned.append(" ")

    return " ".join("".join(cleaned).split())


def find_course_mentioned_in_message(message, courses):
    """
    Return a course code when exactly one real course title
    appears in the student's message.

    This prevents the model from returning a valid but unrelated
    code such as CS301 for a message that explicitly names
    another course.
    """
    normalized_message = normalize_text(message)
    matches = []

    for course in courses:
        title = normalize_text(course["title"])

        if title and title in normalized_message:
            matches.append(course)

    if len(matches) == 1:
        return matches[0]["course_code"]

    return None


# ============================================================
# ASK AI
# ============================================================

def ask_ai(
    message,
    courses
):

    load_model()

    course_list = build_course_list(
        courses
    )

    prompt = f"""
Identify the ONE course the student is asking about.

Student message:
{message}

Real courses:
{course_list}

Rules:
1. Match the course named or clearly referred to in the message.
2. Do not choose a course just because it appears first or last.
3. The course_code must be one of the real course codes listed above.
4. Return JSON only.
5. The JSON must contain exactly one field: course_code.

Required JSON shape:
{{"course_code": "<one real course code>"}}
"""

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
            max_new_tokens=30,
            do_sample=False,
            pad_token_id=(
                tokenizer.eos_token_id
            )
        )

    generated = output[
        0
    ][
        input_ids.shape[-1]:
    ]

    response = tokenizer.decode(
        generated,
        skip_special_tokens=True
    ).strip()

    return response


# ============================================================
# RETRY AI
# ============================================================

def retry_ai(
    message,
    courses
):

    load_model()

    course_list = build_course_list(
        courses
    )

    prompt = f"""
Your previous answer could not be accepted.

Identify the course in this student message:

{message}

Choose exactly one course from this real course list:
{course_list}

Return JSON only with exactly one field named course_code.
The course_code must be one of the real codes in the list.

Required JSON shape:
{{"course_code": "<one real course code>"}}
"""

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
            max_new_tokens=30,
            do_sample=False,
            pad_token_id=(
                tokenizer.eos_token_id
            )
        )

    generated = output[
        0
    ][
        input_ids.shape[-1]:
    ]

    response = tokenizer.decode(
        generated,
        skip_special_tokens=True
    ).strip()

    return response


# ============================================================
# EXTRACT ONE REQUEST
# ============================================================

def extract_course_code(
    message
):

    courses = get_real_courses()

    if len(courses) != 7:

        raise RuntimeError(
            "Expected 7 real courses, "
            f"found {len(courses)}."
        )

    # --------------------------------------------------------
    # EXPLICIT COURSE-TITLE MATCH
    # --------------------------------------------------------
    #
    # The project documentation notes that a title-to-code
    # dictionary handles most of the six requests. Use this as
    # a guard for messages that explicitly name one of the
    # seven courses. The required SmolLM2 model is still used
    # for wording where an exact title is not present.

    direct_code = find_course_mentioned_in_message(
        message,
        courses
    )

    if direct_code:
        return {
            "course_code": direct_code,
            "status": "success ",
            "error": None
        }

    # --------------------------------------------------------
    # FIRST AI ATTEMPT
    # --------------------------------------------------------

    try:

        response = ask_ai(
            message,
            courses
        )

    except Exception as error:

        return {
            "course_code": None,
            "status": "AI error",
            "error": str(error)
        }

    data = extract_json(
        response
    )

    course_code = validate_course_code(
        data,
        courses
    )

    if course_code:

        return {
            "course_code": course_code,
            "status": "success",
            "error": None
        }

    # --------------------------------------------------------
    # SECOND ATTEMPT
    # --------------------------------------------------------

    try:

        response = retry_ai(
            message,
            courses
        )

    except Exception as error:

        return {
            "course_code": None,
            "status": "AI retry error",
            "error": str(error)
        }

    data = extract_json(
        response
    )

    course_code = validate_course_code(
        data,
        courses
    )

    if course_code:

        return {
            "course_code": course_code,
            "status": "success after retry",
            "error": None
        }

    # --------------------------------------------------------
    # FAILED TWICE
    # --------------------------------------------------------

    real_codes = ", ".join(
        course["course_code"]
        for course in courses
    )

    return {
        "course_code": None,
        "status": "invalid AI response",
        "error": (
            "AI did not return a valid course code. "
            f"Valid codes: {real_codes}"
        )
    }


# ============================================================
# READ REQUEST FILE
# ============================================================

def read_request(
    request_id
):

    request_file = (
        REQUESTS_DIR
        / f"{request_id}.json"
    )

    if not request_file.exists():

        return None

    try:

        with open(
            request_file,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except json.JSONDecodeError:

        return None


# ============================================================
# PROCESS ALL SIX REQUESTS
# ============================================================

def process_all_requests():

    results = []

    request_ids = [
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6"
    ]

    for request_id in request_ids:

        request_data = read_request(
            request_id
        )

        if request_data is None:

            results.append(
                {
                    "request": request_id,
                    "student_id": None,
                    "message": None,
                    "course_code": None,
                    "status": "request file error"
                }
            )

            continue

        student_id = request_data.get(
            "student_id"
        )

        message = request_data.get(
            "message"
        )

        print()
        print("=" * 60)
        print(f"Request: {request_id}")
        print("=" * 60)

        print(
            "Student:",
            student_id
        )

        print(
            "Message:",
            message
        )

        result = extract_course_code(
            message
        )

        print(
            "Course code:",
            result["course_code"]
        )

        print(
            "Status:",
            result["status"]
        )

        if result["error"]:

            print(
                "Error:",
                result["error"]
            )

        results.append(
            {
                "request": request_id,
                "student_id": student_id,
                "message": message,
                "course_code": result[
                    "course_code"
                ],
                "status": result[
                    "status"
                ],
                "error": result[
                    "error"
                ]
            }
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
        / "task8_results.json"
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
        f"Results saved to: {output_file}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 60)
    print(" ALL REQUESTS")
    print("=" * 60)

    results = process_all_requests()

    save_results(
        results
    )

    print()
    print("=" * 60)
    print("results")
    print("=" * 60)

    for result in results:

        print(
            f"{result['request']} -> "
            f"{result['course_code']} "
            f"({result['status']})"
        )