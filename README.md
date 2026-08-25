Course Enrolment Assistant

An AI-assisted course enrolment system built with Python, FastAPI, HTML/CSS/JavaScript, rule-based eligibility checks, handbook retrieval (RAG), and SmolLM2-1.7B-Instruct.

Project Flow



Main Workflow

Student enters a question or uses an enrolment tool.

HTML/CSS/JavaScript sends the request to FastAPI.

The API identifies the relevant student/course.

The extraction layer maps natural language to a course.

All five enrolment rules are evaluated.

Relevant handbook information is retrieved.

The AI reply layer generates a student-friendly response.

The response is validated and a fallback can be returned if validation fails.

The final response is displayed on the webpage.

Technology Stack

Component

Technology

Frontend

HTML, CSS, JavaScript

Backend

FastAPI

Server

Uvicorn

Database

SQLite

LLM

SmolLM2-1.7B-Instruct

Retrieval

Handbook / RAG

Rules

Python

Version Control

Git / GitHub

Example Prompts and Outputs

R1 — Algorithms

Student: S-104

Prompt: I want to take Algorithms this term.

Course: CS201

Output:

Enrolment is blocked because: CS101 grade missing, needs 40.

R2 — Distributed Systems

Student: S-101

Prompt: Can I add Distributed Systems?

Course: CS310

Output:

Enrolment is blocked because: full, 25 of 25.

R3 — Databases

Student: S-103

Prompt: I would like to join Databases please.

Course: CS202

Output:

Enrolment is blocked because: clashes with MA150 Wed 14:00.

R4 — Machine Learning

Student: S-102

Prompt: Trying to sign up for Machine Learning and it will not let me.

Course: CS301

Output:

Enrolment is blocked because: fees are unpaid; would be 65 credits, limit 60.

Important: R4 has two independent blocking reasons, and both are returned.

R5 — Machine Learning

Student: S-105

Prompt: Machine Learning please, I have done everything it asks for.

Course: CS301

Output:

Enrolment is blocked because: CS201 grade 48, needs 55.

R6 — Data Visualisation

Student: S-106

Prompt: Could I take Data Visualisation?

Course: DS220

Output:

You are eligible to enrol in DS220.

Final Test Results

ID

Expected

Actual

Reasons

Handbook

Reply

Overall

R1

CS201

CS201

PASS

YES

PASS

PASS

R2

CS310

CS310

PASS

YES

PASS

PASS

R3

CS202

CS202

PASS

YES

PASS

PASS

R4

CS301

CS301

PASS

YES

PASS

PASS

R5

CS301

CS301

PASS

YES

PASS

PASS

R6

DS220

DS220

PASS

NO

PASS

PASS

Requests passed: 6/6

Ask AI

The Ask AI feature accepts a student ID and a natural-language question and sends the request to the FastAPI backend.

Example:

Student ID: S-102
Question: Why can't I enrol in Machine Learning?

Expected grounded answer:

Enrolment is blocked because:
- fees are unpaid
- would be 65 credits, limit 60

The AI response is generated using the project's instruction-following model and is grounded by the application's rule results and retrieved handbook information.

Running the Project

Start FastAPI:

uvicorn api:app --reload

Open the webpage:

http://127.0.0.1:8000/

FastAPI documentation:

http://127.0.0.1:8000/docs

Project Structure

course_enrollment_assistant/
├── api.py
├── assistant.py
├── check_data.py
├── comparison.py
├── extract.py
├── load.py
├── reply.py
├── rules.py
├── search.py
├── index.html
├── script.js
├── style.css
├── data/
├── handbook/
├── enrolment.db
├── extract_results.json
├── task8_results.json
├── task9_results.json
├── README.md
└── course_enrollment_flow.png

Key Outcome

The complete validation achieved 6/6 requests passed.

The system correctly identified courses, returned all applicable enrolment reasons, retrieved handbook evidence where required, and generated valid replies.

Model

The project documentation specifies SmolLM2-1.7B-Instruct. It is used for instruction-following and natural-language reply generation. Deterministic enrolment decisions remain grounded in the application's rules and retrieved information.
