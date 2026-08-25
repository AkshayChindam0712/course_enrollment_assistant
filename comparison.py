import requests


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "http://127.0.0.1:8000"

REQUEST_IDS = [
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6"
]


# ============================================================
# EXPECTED RESULTS
#
# These are the expected outcomes from the project data.
# ============================================================

EXPECTED = {
    "R1": {
        "course_code": "CS201",
        "reasons": [
            "prerequisite"
        ]
    },

    "R2": {
        "course_code": "CS310",
        "reasons": [
            "capacity"
        ]
    },

    "R3": {
        "course_code": "CS202",
        "reasons": [
            "clash"
        ]
    },

    "R4": {
        "course_code": "CS301",
        "reasons": [
            "fees are unpaid",
            "would be 65 credits, limit 60"
        ]
    },

    "R5": {
        "course_code": "CS301",
        "reasons": [
            "prerequisite"
        ]
    },

    "R6": {
        "course_code": "DS220",
        "reasons": []
    }
}


# ============================================================
# GET ONE REQUEST
# ============================================================

def get_result(request_id):

    url = (
        f"{BASE_URL}"
        f"/requests/{request_id}/answer"
    )

    try:

        response = requests.get(
            url,
            timeout=300
        )

        if response.status_code != 200:

            return {
                "request_id": request_id,
                "success": False,
                "error": response.text
            }

        result = response.json()

        if not result.get("ok"):

            return {
                "request_id": request_id,
                "success": False,
                "error": result.get(
                    "error"
                )
            }

        data = result.get(
            "data",
            {}
        )

        return {
            "request_id": request_id,
            "success": True,
            "course_code": data.get(
                "course_code"
            ),
            "reasons": data.get(
                "reasons",
                []
            ),
            "handbook": data.get(
                "handbook",
                []
            ),
            "reply": data.get(
                "reply",
                ""
            ),
            "reply_valid": data.get(
                "reply_valid"
            ),
            "eligible": data.get(
                "eligible"
            )
        }

    except requests.exceptions.ConnectionError:

        return {
            "request_id": request_id,
            "success": False,
            "error": (
                "Could not connect to API. "
                "Start it with: "
                "uvicorn api:app --reload"
            )
        }

    except Exception as error:

        return {
            "request_id": request_id,
            "success": False,
            "error": str(error)
        }


# ============================================================
# NORMALISE REASONS
# ============================================================

def reason_type(reason):

    text = str(reason).lower()

    if "fee" in text:
        return "fees"

    if "credit" in text:
        return "credit_limit"

    if (
        "prerequisite" in text
        or "grade" in text
        or "completed" in text
    ):
        return "prerequisite"

    if (
        "capacity" in text
        or "full" in text
    ):
        return "capacity"

    if (
        "clash" in text
        or "timetable" in text
        or "schedule" in text
    ):
        return "clash"

    return text


def normalise_reasons(reasons):

    return {
        reason_type(reason)
        for reason in reasons
    }


# ============================================================
# CHECK EXPECTED RESULT
# ============================================================

def check_result(
    request_id,
    actual
):

    expected = EXPECTED[
        request_id
    ]

    # --------------------------------------------------------
    # Course check
    # --------------------------------------------------------

    course_correct = (
        actual.get("course_code")
        == expected["course_code"]
    )

    # --------------------------------------------------------
    # Reasons check
    # --------------------------------------------------------

    actual_reasons = normalise_reasons(
        actual.get("reasons", [])
    )

    expected_reasons = {
        reason_type(reason)
        for reason in expected["reasons"]
    }

    reasons_correct = (
        actual_reasons
        == expected_reasons
    )

    # --------------------------------------------------------
    # Reply validation
    # --------------------------------------------------------

    reply_valid = (
        actual.get("reply_valid")
        is True
    )

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    correct = (
        course_correct
        and reasons_correct
        and reply_valid
    )

    return {
        "course_correct": course_correct,
        "reasons_correct": reasons_correct,
        "reply_valid": reply_valid,
        "correct": correct
    }


# ============================================================
# PRINT ONE RESULT
# ============================================================

def print_result(
    request_id,
    actual,
    comparison
):

    print()
    print("-" * 70)
    print(
        f"Request: {request_id}"
    )
    print("-" * 70)

    if not actual["success"]:

        print("Status: FAILED")
        print(
            f"Error: {actual['error']}"
        )
        return

    print(
        f"Course: "
        f"{actual['course_code']}"
    )

    print(
        "Reasons:"
    )

    if actual["reasons"]:

        for reason in actual["reasons"]:
            print(
                f"  - {reason}"
            )

    else:

        print("  - None")

    print(
        "Handbook:"
    )

    if actual["handbook"]:

        for page in actual["handbook"]:
            print(
                f"  - {page}"
            )

    else:

        print("  - None")

    print(
        f"Eligible: "
        f"{actual['eligible']}"
    )

    print(
        f"Reply valid: "
        f"{actual['reply_valid']}"
    )

    print()
    print("Reply:")

    print(
        actual["reply"]
    )

    print()
    print("Comparison:")

    print(
        f"  Course: "
        f"{'PASS' if comparison['course_correct'] else 'FAIL'}"
    )

    print(
        f"  Reasons: "
        f"{'PASS' if comparison['reasons_correct'] else 'FAIL'}"
    )

    print(
        f"  Reply: "
        f"{'PASS' if comparison['reply_valid'] else 'FAIL'}"
    )

    print(
        f"  Overall: "
        f"{'PASS' if comparison['correct'] else 'FAIL'}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("ENROLMENT ASSISTANT CHECK")
    print("=" * 70)

    results = []

    for request_id in REQUEST_IDS:

        print()
        print(
            f"Checking {request_id}..."
        )

        actual = get_result(
            request_id
        )

        if actual["success"]:

            comparison = check_result(
                request_id,
                actual
            )

        else:

            comparison = {
                "course_correct": False,
                "reasons_correct": False,
                "reply_valid": False,
                "correct": False
            }

        results.append(
            (
                request_id,
                actual,
                comparison
            )
        )

    # ========================================================
    # DETAILED RESULTS
    # ========================================================

    for (
        request_id,
        actual,
        comparison
    ) in results:

        print_result(
            request_id,
            actual,
            comparison
        )

    # ========================================================
    # FINAL TABLE
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL COMPARISON")
    print("=" * 70)

    print()

    print(
        f"{'ID':<6}"
        f"{'Expected':<12}"
        f"{'Actual':<12}"
        f"{'Reasons':<10}"
        f"{'Handbook':<12}"
        f"{'Reply':<8}"
    )

    print("-" * 70)

    for (
        request_id,
        actual,
        comparison
    ) in results:

        expected_course = EXPECTED[
            request_id
        ]["course_code"]

        if actual["success"]:

            actual_course = (
                actual["course_code"]
            )

            reasons_status = (
                "PASS"
                if comparison[
                    "reasons_correct"
                ]
                else "FAIL"
            )

            handbook_status = (
                "YES"
                if actual["handbook"]
                else "NO"
            )

            reply_status = (
                "PASS"
                if comparison[
                    "reply_valid"
                ]
                else "FAIL"
            )

        else:

            actual_course = "ERROR"
            reasons_status = "FAIL"
            handbook_status = "NO"
            reply_status = "FAIL"

        print(
            f"{request_id:<6}"
            f"{expected_course:<12}"
            f"{actual_course:<12}"
            f"{reasons_status:<10}"
            f"{handbook_status:<12}"
            f"{reply_status:<8}"
        )

    # ========================================================
    # TOTAL
    # ========================================================

    passed = sum(
        1
        for (
            _,
            _,
            comparison
        ) in results
        if comparison["correct"]
    )

    print()
    print("=" * 70)

    print(
        f"Requests passed: "
        f"{passed}/{len(REQUEST_IDS)}"
    )

    print("=" * 70)
    print()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()