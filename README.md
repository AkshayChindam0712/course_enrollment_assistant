# Course Enrolment Assistant

This project implements the ten tasks in `Course_Enrolment_Assistant_Tasks.docx`.

## Architecture

Student request -> AI course extraction -> five SQL-backed rules -> handbook vector search -> AI reply -> Streamlit page.

The AI has two jobs only:
1. Extract a real course code from the student's message.
2. Turn rule reasons + retrieved handbook text into a short student-facing reply.

The Python code owns the database, rules and handbook search.

## Data-quality findings

`check_data.py` identifies two real source-data issues:
- `students.csv`: S-106 has `fees_status` written as `PAID` while the other paid records use `paid`.
- `students.csv`: S-107 has a missing `year`.

The loader normalises fees status to lowercase and keeps the unused year as SQL NULL. Source CSVs are not edited.

## Setup

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python check_data.py
python load.py
python test_rules.py
```

## API

```bash
uvicorn api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

Endpoints:
- `GET /students/{id}`
- `GET /students/{id}/enrolments`
- `GET /courses`
- `GET /courses/{code}`
- `GET /check/{student_id}/{course_code}`
- `GET /requests/{request_id}`

## Page

In another terminal:

```bash
streamlit run app.py
```

## Handbook search

The first run downloads `BAAI/bge-small-en-v1.5` and embeds all eight handbook pages. Run:

```bash
python search.py
```

The task specifies `BAAI/bge-small-en-v1.5` for retrieval and `HuggingFaceTB/SmolLM2-1.7B-Instruct` for the AI calls.

## AI

`ai.py` follows the task requirements:
- model loaded once;
- deterministic generation (`do_sample=False`);
- message + list of seven real course codes/titles;
- JSON extraction from first `{` to last `}`;
- invented codes rejected;
- no-JSON output raises a controlled error so the caller can retry once.

For a production version, add the retry/validation orchestration around these primitives and never let the model approve an enrolment.

## Expected rule results

See `task10_results.md` and run `python test_rules.py`.

Important handbook constraints:
- all blocking reasons should be shown together;
- a full course has no waiting list;
- only current enrolments count toward the 60-credit limit;
- completed courses count for prerequisites only when the grade meets the minimum;
- timetable clashes are any overlap on the same day;
- a waiver may be recommended but cannot itself approve enrolment.
