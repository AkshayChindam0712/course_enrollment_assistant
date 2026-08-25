const API = "http://127.0.0.1:8000";


// ======================================================
// Helper
// ======================================================

function esc(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


async function getAPI(url) {

    const response = await fetch(API + url);

    const data = await response.json();

    if (!response.ok) {
        throw new Error(
            data.detail ||
            data.error ||
            "API request failed"
        );
    }

    return data;
}


// ======================================================
// 1. STUDENT LOOKUP
// GET /students/{student_id}
// ======================================================

async function findStudent() {

    const id =
        document.getElementById("studentId")
        .value
        .trim()
        .toUpperCase();

    const result =
        document.getElementById("studentResult");

    if (!id) {
        result.innerHTML =
            `<div class="error">Please enter a Student ID.</div>`;
        return;
    }

    result.innerHTML = "⏳ Loading student...";

    try {

        const response =
            await getAPI(
                `/students/${encodeURIComponent(id)}`
            );

        const s = response.data;

        result.innerHTML = `
            <div class="result">

                <h3>👨‍🎓 ${esc(s.name)}</h3>

                <p>
                    <strong>Student ID:</strong>
                    ${esc(s.student_id)}
                </p>

                <p>
                    <strong>Year:</strong>
                    ${esc(s.year)}
                </p>

                <p>
                    <strong>Programme:</strong>
                    ${esc(s.programme)}
                </p>

                <p>
                    <strong>Fees:</strong>
                    ${esc(s.fees_status)}
                </p>

            </div>
        `;

        // Also load their enrolments
        await loadStudentEnrolments(id);

    } catch (error) {

        result.innerHTML =
            `<div class="error">❌ ${esc(error.message)}</div>`;
    }
}


// ======================================================
// STUDENT ENROLMENTS
// GET /students/{student_id}/enrolments
// ======================================================

async function loadStudentEnrolments(id) {

    const result =
        document.getElementById("studentResult");

    try {

        const response =
            await getAPI(
                `/students/${encodeURIComponent(id)}/enrolments`
            );

        const enrolments =
            response.data || [];

        let html = `
            <h3>📚 Enrolments</h3>
        `;

        if (!enrolments.length) {

            html +=
                `<p>No enrolments found.</p>`;

        } else {

            html += `
                <table>
                    <tr>
                        <th>Course</th>
                        <th>Title</th>
                        <th>Status</th>
                        <th>Grade</th>
                    </tr>
            `;

            enrolments.forEach(e => {

                html += `
                    <tr>
                        <td>${esc(e.course_code)}</td>
                        <td>${esc(e.title)}</td>
                        <td>${esc(e.status)}</td>
                        <td>${esc(e.grade ?? "-")}</td>
                    </tr>
                `;

            });

            html += `</table>`;
        }

        result.innerHTML += html;

    } catch (error) {

        result.innerHTML +=
            `<div class="error">
                Could not load enrolments.
             </div>`;
    }
}


// ======================================================
// 2. COURSE LIST
// GET /courses
// ======================================================

async function loadCourses() {

    const container =
        document.getElementById("courseList");

    container.innerHTML =
        `<div class="loading">
            ⏳ Loading courses...
         </div>`;

    try {

        const response =
            await getAPI("/courses");

        const courses =
            response.data || [];

        if (!courses.length) {

            container.innerHTML =
                `<div class="empty">
                    No courses found.
                 </div>`;

            return;
        }

        container.innerHTML =
            courses.map(course => `

                <div class="course-item
                    ${course.full ? "full-course" : ""}">

                    <div class="course-header">

                        <h3>
                            ${esc(course.course_code)}
                            —
                            ${esc(course.title)}
                        </h3>

                        ${
                            course.full
                            ? `<span class="badge full">
                                FULL
                               </span>`
                            : `<span class="badge available">
                                AVAILABLE
                               </span>`
                        }

                    </div>

                    <p>
                        📅 ${esc(course.day)}
                    </p>

                    <p>
                        🕐
                        ${esc(course.start)}
                        -
                        ${esc(course.end)}
                    </p>

                    <p>
                        🎓
                        ${esc(course.credits)}
                        credits
                    </p>

                    <p>
                        👥
                        ${esc(course.enrolled_now)}
                        /
                        ${esc(course.capacity)}
                    </p>

                </div>

            `).join("");

    } catch (error) {

        container.innerHTML =
            `<div class="error">
                ❌ ${esc(error.message)}
             </div>`;
    }
}


// ======================================================
// 3. CHECK ENROLLMENT
// GET /check/{student_id}/{course_code}
// ======================================================

async function checkEnrollment() {

    const student =
        document.getElementById("checkStudent")
        .value
        .trim()
        .toUpperCase();

    const course =
        document.getElementById("courseCode")
        .value
        .trim()
        .toUpperCase();

    const result =
        document.getElementById("checkResult");

    if (!student || !course) {

        result.innerHTML =
            `<div class="error">
                Please enter Student ID and Course Code.
             </div>`;

        return;
    }

    result.innerHTML =
        `<div class="loading">
            ⏳ Checking all five enrolment rules...
         </div>`;

    try {

        const response =
            await getAPI(
                `/check/${encodeURIComponent(student)}/${encodeURIComponent(course)}`
            );

        const data =
            response.data;

        const reasons =
            data.reasons || [];

        result.innerHTML = `

            <div class="${
                data.eligible
                ? "success"
                : "error"
            }">

                <h3>
                    ${
                        data.eligible
                        ? "✅ Eligible for Enrolment"
                        : "❌ Enrolment Blocked"
                    }
                </h3>

                <p>
                    <strong>Student:</strong>
                    ${esc(data.student_id)}
                </p>

                <p>
                    <strong>Course:</strong>
                    ${esc(data.course_code)}
                </p>

            </div>

            <div class="result">

                <h3>⚠️ Reasons</h3>

                ${
                    reasons.length
                    ? `
                        <ul>
                            ${reasons.map(reason =>
                                `<li>${esc(reason)}</li>`
                            ).join("")}
                        </ul>
                      `
                    : `
                        <p>
                            ✅ No blocking reasons.
                        </p>
                      `
                }

            </div>
        `;

    } catch (error) {

        console.error(
            "CHECK ENROLLMENT ERROR:",
            error
        );

        result.innerHTML =
            `<div class="error">
                ❌ ${esc(error.message)}
             </div>`;
    }
}


// ======================================================
// 4. ASK AI
// POST /ask
// ======================================================

document
    .getElementById("ask-form")
    .addEventListener("submit", askAI);


async function askAI(event) {
    event.preventDefault();

    const student = document.getElementById("ask-student-id").value.trim();
    const question = document.getElementById("question").value.trim();
    const loading = document.getElementById("ask-loading");
    const message = document.getElementById("ask-message");
    const result = document.getElementById("ask-result");

    if (!student || !question) {
        message.innerHTML =
            `<div class="error">❌ Enter Student ID and your question.</div>`;
        return;
    }

    loading.classList.remove("hidden");
    message.innerHTML = "";
    result.innerHTML = "";

    try {
        message.innerHTML = "🔎 Generating AI reply...";

        const url =
            `${API}/ask?student_id=${encodeURIComponent(student)}` +
            `&message=${encodeURIComponent(question)}`;

        console.log("ASK URL:", url);

        const response = await fetch(url, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            }
        });

        const data = await response.json();

        console.log("ASK RESPONSE:", data);

        if (!response.ok) {
            throw new Error(
                data.detail ||
                data.error ||
                "AI request failed"
            );
        }

        const d = data.data || data;

        const reasons = d.reasons || [];
        const handbook = d.handbook || [];

        message.innerHTML =
            `<div class="success">✅ AI response generated.</div>`;

        result.innerHTML = `
            <div class="result">

                <h3>🤖 Answer</h3>
                <p>${esc(d.reply || "No reply returned.")}</p>

                <h3>📚 Course</h3>
                <p>
                    <strong>${esc(d.course_code || "Unknown")}</strong>
                    ${
                        d.course_title
                        ? " — " + esc(d.course_title)
                        : ""
                    }
                </p>

                <h3>🎯 Eligibility</h3>
                <p>
                    ${
                        d.eligible
                        ? "✅ You are eligible to enrol."
                        : "❌ You are not currently eligible."
                    }
                </p>

                <h3>⚠️ Reasons</h3>

                ${
                    reasons.length
                    ? `<ul>
                        ${reasons.map(r =>
                            `<li>${esc(r)}</li>`
                        ).join("")}
                       </ul>`
                    : "<p>✅ No blocking reasons.</p>"
                }

                <h3>📖 Handbook</h3>

                ${
                    handbook.length
                    ? `<ul>
                        ${handbook.map(h =>
                            `<li>📖 ${esc(
                                typeof h === "string"
                                    ? h
                                    : h.file || h.name || h
                            )}</li>`
                        ).join("")}
                       </ul>`
                    : "<p>No handbook pages retrieved.</p>"
                }

                ${
                    d.reply_valid !== undefined
                    ? `<p>
                        <strong>Reply validation:</strong>
                        ${d.reply_valid ? "✅ Valid" : "⚠️ Failed"}
                       </p>`
                    : ""
                }

            </div>
        `;

    } catch (error) {

        console.error("ASK AI ERROR:", error);

        message.innerHTML =
            `<div class="error">❌ ${esc(error.message)}</div>`;

    } finally {
        loading.classList.add("hidden");
    }
}