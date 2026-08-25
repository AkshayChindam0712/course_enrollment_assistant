import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from rules import check_all, reasons
from search import search


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_NAME = "HuggingFaceTB/SmolLM2-1.7B-Instruct"

REQUESTS_DIR = Path("data") / "requests"
HANDBOOK_DIR = Path("data") / "handbook"


# ============================================================
# REAL COURSES
# ============================================================

COURSES = {
    "CS101": "Programming Foundations",
    "CS201": "Algorithms",
    "CS202": "Databases",
    "CS301": "Machine Learning",
    "CS310": "Distributed Systems",
    "MA150": "Statistics",
    "DS220": "Data Visualisation",
}


# ============================================================
# LOAD AI MODEL ONCE
# ============================================================

print("Loading AI model...")

tokenizer = AutoTokenizer.from_pretrained(
    MODEL_NAME
)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    dtype=torch.float32
)

model.eval()

print("AI model loaded.")
print()


# ============================================================
# COURSE EXTRACTION
# ============================================================

def validate_reply(reply, rule_reasons, handbook_files):
    """
    Make sure the AI response contains every required
    reason and handbook filename.
    """

    reply_lower = reply.lower()

    missing_reasons = []

    for reason in rule_reasons:
        if reason.lower() not in reply_lower:
            missing_reasons.append(reason)

    missing_files = []

    for filename in handbook_files:
        if filename.lower() not in reply_lower:
            missing_files.append(filename)

    if missing_reasons or missing_files:
        return False, {
            "missing_reasons": missing_reasons,
            "missing_files": missing_files
        }

    return True, None
    
def ask_ai_for_course(message):

    course_list = "\n".join(
        f"{code}: {title}"
        for code, title in COURSES.items()
    )

    prompt = f"""
Identify which course the student is asking about.

Student message:
{message}

Real courses:
{course_list}

Return JSON only:
{{"course_code": "CODE"}}

The course_code must be one of the real course codes listed above.
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

    if hasattr(inputs, "input_ids"):
        input_ids = inputs.input_ids
        attention_mask = inputs.attention_mask
    else:
        input_ids = inputs
        attention_mask = torch.ones_like(input_ids)

    with torch.no_grad():

        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=20,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = output[0][input_ids.shape[-1]:]

    return tokenizer.decode(
        generated,
        skip_special_tokens=True
    )


def parse_course_code(reply):

    start = reply.find("{")
    end = reply.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    json_text = reply[start:end + 1]

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    course_code = data.get("course_code")

    if not isinstance(course_code, str):
        return None

    course_code = course_code.strip().upper()

    if course_code not in COURSES:
        return None

    return course_code


def extract_course(message):

    for attempt in range(2):

        reply = ask_ai_for_course(message)

        course_code = parse_course_code(reply)

        if course_code is not None:
            return course_code

    valid_courses = ", ".join(COURSES.keys())

    raise ValueError(
        "The AI could not identify a valid course. "
        f"Valid course codes are: {valid_courses}"
    )


# ============================================================
# HANDBOOK TEXT
# ============================================================

def read_handbook(filename):

    path = HANDBOOK_DIR / filename

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8"
    ).strip()


def handbook_for_reasons(rule_reasons):

    """
    Search the handbook using the reasons that blocked
    the student and collect the relevant handbook text.
    """

    handbook_sections = []

    used_files = set()

    for reason in rule_reasons:

        results = search(
            reason,
            k=3
        )

        if not results:
            continue

        # Use the best matching handbook page.
        best = results[0]

        filename = best["file"]

        if filename in used_files:
            continue

        text = read_handbook(filename)

        if text:

            handbook_sections.append(
                f"[{filename}]\n{text}"
            )

            used_files.add(filename)

    return "\n\n".join(handbook_sections)


# ============================================================
# WRITE FINAL STUDENT REPLY
# ============================================================

def write_reply(
    student_id,
    course_code,
    rule_reasons,
    handbook_text
):

    reasons_text = "\n".join(
        f"- {reason}"
        for reason in rule_reasons
    )

    prompt = f"""
Write a concise student-facing enrolment decision.

Student ID:
{student_id}

Requested course:
{course_code}

Rule reasons:
{reasons_text}

Relevant handbook:
{handbook_text}

Instructions:
- Include EVERY rule reason.
- Explain briefly why each reason blocks enrolment.
- Tell the student what they can do next.
- Mention the relevant handbook filename.
- Do not copy the handbook.
- Do not invent information.
- Do not promise that fees will be cleared.
- Do not say "Dear Student".
- Return only the student-facing message.
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

    if hasattr(inputs, "input_ids"):
        input_ids = inputs.input_ids
        attention_mask = inputs.attention_mask
    else:
        input_ids = inputs
        attention_mask = torch.ones_like(input_ids)

    with torch.no_grad():

        output = model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            max_new_tokens=80,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )

    generated = output[0][input_ids.shape[-1]:]

    reply = tokenizer.decode(
        generated,
        skip_special_tokens=True
    )

    return reply.strip()


# ============================================================
# PROCESS ONE REQUEST
# ============================================================

def process_request(request):

    student_id = request["student_id"]
    message = request["message"]

    # --------------------------------------------------------
    # 1. AI extracts course
    # --------------------------------------------------------

    course_code = extract_course(message)

    # --------------------------------------------------------
    # 2. Run all five rules
    # --------------------------------------------------------

    rule_results = check_all(
        student_id,
        course_code
    )

    rule_reasons = reasons(
        rule_results
    )

    # --------------------------------------------------------
    # 3. Approved
    # --------------------------------------------------------

    if not rule_reasons:

        return {
            "request": request["request"],
            "student_id": student_id,
            "course_code": course_code,
            "rules": rule_results,
            "reasons": [],
            "reply": (
                f"You can enrol in {course_code}. "
                "All five enrolment checks passed."
            )
        }

    # --------------------------------------------------------
    # 4. Search handbook
    # --------------------------------------------------------

    handbook_text = handbook_for_reasons(
        rule_reasons
    )

    # --------------------------------------------------------
    # 5. AI writes final response
    # --------------------------------------------------------

    final_reply = write_reply(
        student_id,
        course_code,
        rule_reasons,
        handbook_text
    )

    return {
        "request": request["request"],
        "student_id": student_id,
        "course_code": course_code,
        "rules": rule_results,
        "reasons": rule_reasons,
        "reply": final_reply
    }


# ============================================================
# LOAD REQUESTS
# ============================================================

def load_requests():

    requests = []

    for path in sorted(
        REQUESTS_DIR.glob("R*.json")
    ):

        with path.open(
            "r",
            encoding="utf-8"
        ) as file:

            requests.append(
                json.load(file)
            )

    return requests


# ============================================================
# TEST R4 ONLY
# ============================================================

if __name__ == "__main__":

    requests = load_requests()

    request = next(
        r for r in requests
        if r["request"] == "R4"
    )

    print("=" * 60)
    print("REQUEST")
    print("=" * 60)

    print(
        f"Request: {request['request']}"
    )

    print(
        f"Student: {request['student_id']}"
    )

    print(
        f"Message: {request['message']}"
    )

    print()
    print("Processing...")

    result = process_request(
        request
    )

    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)

    print(
        f"Course: {result['course_code']}"
    )

    print(
        "Reasons:",
        result["reasons"]
    )

    print()
    print("AI reply:")
    print(
        result["reply"]
    )