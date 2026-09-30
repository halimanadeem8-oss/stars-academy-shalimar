from flask import Flask, request, redirect, url_for, session, render_template_string, flash
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = Flask(__name__)

# ============================================================
# SETTINGS
# ============================================================

app.secret_key = "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY"

DATABASE = "academy.db"

# Default login
# CHANGE THESE BEFORE USING THIS FOR A REAL CLIENT
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Google Sign-In
GOOGLE_CLIENT_ID = "312451195394-e1f23atprh8n8v5l3nf9obdmb6mk2pfn.apps.googleusercontent.com"
GOOGLE_ALLOWED_EMAIL = "halima.nadeem8@gmail.com"


# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    db = get_db()

    # Admin table
    db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Students table
    db.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            class_name TEXT NOT NULL,
            fees TEXT NOT NULL DEFAULT 'Unpaid',
            attendance TEXT NOT NULL DEFAULT 'Present'
        )
    """)

    # Attendance table
    db.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            UNIQUE(student_id, attendance_date),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    # Create admin account if it does not exist
    existing_admin = db.execute(
        "SELECT * FROM admins WHERE username = ?",
        (ADMIN_USERNAME,)
    ).fetchone()

    if not existing_admin:
        db.execute(
            "INSERT INTO admins (username, password) VALUES (?, ?)",
            (
                ADMIN_USERNAME,
                generate_password_hash(ADMIN_PASSWORD)
            )
        )

    db.commit()
    db.close()


# ============================================================
# LOGIN PROTECTION
# ============================================================

def login_required(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("login"))
        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# COMMON HTML
# ============================================================

BASE_STYLE = """
<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #f4f6fb;
    color: #172033;
}

a {
    text-decoration: none;
}

button,
input,
select {
    font-family: inherit;
}

.navbar {
    height: 70px;
    background: #101b3d;
    color: white;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 30px;
    box-shadow: 0 3px 12px rgba(0,0,0,0.12);
}

.brand {
    font-size: 21px;
    font-weight: bold;
}

.brand small {
    display: block;
    font-size: 11px;
    color: #d6b45c;
    margin-top: 3px;
}

.nav-right {
    display: flex;
    align-items: center;
    gap: 15px;
}

.logout-btn {
    background: #d9534f;
    color: white;
    padding: 10px 16px;
    border-radius: 7px;
    font-weight: bold;
}

.logout-btn:hover {
    background: #c73f3b;
}

.container {
    max-width: 1250px;
    margin: auto;
    padding: 30px;
}

.page-title {
    margin-bottom: 5px;
    font-size: 30px;
}

.subtitle {
    color: #697386;
    margin-top: 0;
    margin-bottom: 25px;
}

/* =========================
   DASHBOARD CARDS
========================= */

.stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    margin-bottom: 25px;
}

.stat-card {
    background: white;
    border-radius: 14px;
    padding: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.07);
    border-left: 5px solid #d6b45c;
}

.stat-title {
    color: #697386;
    font-size: 14px;
    margin-bottom: 10px;
}

.stat-number {
    font-size: 36px;
    font-weight: bold;
}

.present-card {
    border-left-color: #2e9d62;
}

.absent-card {
    border-left-color: #d9534f;
}

.total-card {
    border-left-color: #d6b45c;
}

/* =========================
   GRAPH
========================= */

.dashboard-grid {
    display: grid;
    grid-template-columns: 1.5fr 1fr;
    gap: 25px;
}

.panel {
    background: white;
    border-radius: 14px;
    padding: 25px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.07);
}

.panel h2 {
    margin-top: 0;
}

.graph {
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 70px;
    height: 280px;
    padding: 20px;
    border-bottom: 2px solid #ddd;
}

.bar-wrapper {
    height: 230px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    align-items: center;
    width: 100px;
}

.bar {
    width: 70px;
    min-height: 8px;
    border-radius: 8px 8px 0 0;
}

.present-bar {
    background: #2e9d62;
}

.absent-bar {
    background: #d9534f;
}

.bar-number {
    font-weight: bold;
    margin-bottom: 8px;
}

.bar-label {
    margin-top: 10px;
    font-weight: bold;
}

.attendance-percent {
    font-size: 42px;
    font-weight: bold;
    color: #101b3d;
    margin: 20px 0 5px;
}

.date-text {
    color: #697386;
}

/* =========================
   MENU
========================= */

.menu-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
    margin-top: 20px;
}

.menu-button {
    background: #101b3d;
    color: white;
    padding: 16px;
    border-radius: 9px;
    text-align: center;
    font-weight: bold;
}

.menu-button:hover {
    background: #182957;
}

/* =========================
   STUDENTS
========================= */

.toolbar {
    background: white;
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.07);
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 20px;
}

.search-box,
.select-box {
    padding: 13px;
    border: 1px solid #d7dce5;
    border-radius: 8px;
    outline: none;
    font-size: 14px;
}

.search-box {
    flex: 1;
}

.search-box:focus,
.select-box:focus {
    border-color: #d6b45c;
}

.gold-button {
    background: #d6b45c;
    color: #101b3d;
    padding: 13px 18px;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    cursor: pointer;
}

.gold-button:hover {
    background: #c8a54d;
}

.blue-button {
    background: #101b3d;
    color: white;
    padding: 9px 13px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
}

.red-button {
    background: #d9534f;
    color: white;
    padding: 9px 13px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
}

.green-button {
    background: #2e9d62;
    color: white;
    padding: 9px 13px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
}

.student-table-wrapper {
    background: white;
    border-radius: 14px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.07);
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th {
    background: #101b3d;
    color: white;
    padding: 15px;
    text-align: left;
}

td {
    padding: 14px 15px;
    border-bottom: 1px solid #edf0f5;
}

tr:hover {
    background: #fafbfc;
}

.status {
    display: inline-block;
    padding: 6px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: bold;
}

.paid {
    background: #dff5e8;
    color: #227a4b;
}

.unpaid {
    background: #fde3e2;
    color: #b43a36;
}

.partial {
    background: #fff2cc;
    color: #876d00;
}

.present-status {
    background: #dff5e8;
    color: #227a4b;
}

.absent-status {
    background: #fde3e2;
    color: #b43a36;
}

.not-marked-status {
    background: #eef1f5;
    color: #697386;
}

.action-buttons {
    display: flex;
    gap: 7px;
}

/* =========================
   FORMS
========================= */

.form-card {
    max-width: 650px;
    margin: auto;
    background: white;
    padding: 30px;
    border-radius: 14px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.07);
}

.form-group {
    margin-bottom: 18px;
}

.form-group label {
    display: block;
    margin-bottom: 7px;
    font-weight: bold;
}

.form-group input,
.form-group select {
    width: 100%;
    padding: 13px;
    border: 1px solid #d7dce5;
    border-radius: 8px;
}

.form-submit {
    width: 100%;
    padding: 14px;
    background: #101b3d;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    cursor: pointer;
}

.form-submit:hover {
    background: #182957;
}

/* =========================
   ALERTS
========================= */

.alert {
    padding: 13px 17px;
    border-radius: 8px;
    margin-bottom: 18px;
    background: #fff2cc;
    color: #705c00;
}

.success {
    background: #dff5e8;
    color: #227a4b;
}

.error {
    background: #fde3e2;
    color: #a82f2b;
}

/* =========================
   LOGIN
========================= */

.login-page {
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    background: linear-gradient(135deg, #101b3d, #1d2d5a);
    padding: 20px;
}

.login-box {
    width: 100%;
    max-width: 420px;
    background: white;
    padding: 40px;
    border-radius: 18px;
    box-shadow: 0 15px 45px rgba(0,0,0,0.25);
}

.login-title {
    text-align: center;
    color: #101b3d;
    font-size: 30px;
    margin-bottom: 5px;
}

.login-subtitle {
    text-align: center;
    color: #697386;
    margin-bottom: 30px;
}

.login-button {
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 8px;
    background: #d6b45c;
    color: #101b3d;
    font-weight: bold;
    cursor: pointer;
    font-size: 16px;
}

.login-button:hover {
    background: #c8a54d;
}

.back-button {
    display: inline-block;
    margin-bottom: 20px;
    color: #101b3d;
    font-weight: bold;
}

/* =========================
   RESPONSIVE
========================= */

@media (max-width: 850px) {

    .stats {
        grid-template-columns: 1fr;
    }

    .dashboard-grid {
        grid-template-columns: 1fr;
    }

    .toolbar {
        flex-direction: column;
        align-items: stretch;
    }

    .menu-grid {
        grid-template-columns: 1fr;
    }

    .navbar {
        padding: 0 15px;
    }

    .container {
        padding: 20px 15px;
    }

    .brand {
        font-size: 17px;
    }

    .graph {
        gap: 35px;
    }
}

</style>
"""


# ============================================================
# LOGIN PAGE
# ============================================================

LOGIN_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Stars Academy | Login</title>
    {{ style|safe }}
</head>

<body>

<div class="login-page">

    <div class="login-box">

        <h1 class="login-title">Stars Academy</h1>

        <p class="login-subtitle">
            Shalimar Branch<br>
            Academy Management System
        </p>

        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert {{ category }}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endwith %}

        <form method="POST">

            <div class="form-group">
                <label>Username</label>
                <input
                    type="text"
                    name="username"
                    placeholder="Enter username"
                    required
                >
            </div>

            <div class="form-group">
                <label>Password</label>
                <input
                    type="password"
                    name="password"
                    placeholder="Enter password"
                    required
                >
            </div>

            <button class="login-button" type="submit">
                LOGIN
            </button>

        </form>

        <div style="display:flex;align-items:center;gap:10px;margin:24px 0 18px;">
            <div style="height:1px;background:#e1e5ec;flex:1;"></div>
            <span style="color:#697386;font-size:13px;">OR</span>
            <div style="height:1px;background:#e1e5ec;flex:1;"></div>
        </div>

        <div id="google-login-button" style="display:flex;justify-content:center;"></div>
        <p id="google-login-message" style="display:none;text-align:center;color:#b43a36;font-size:13px;margin-top:12px;"></p>

        <script src="https://accounts.google.com/gsi/client" async defer></script>
        <script>
            window.onload = function () {
                if (window.google && google.accounts && google.accounts.id) {
                    google.accounts.id.initialize({
                        client_id: "{{ google_client_id }}",
                        callback: handleGoogleResponse
                    });
                    google.accounts.id.renderButton(
                        document.getElementById("google-login-button"),
                        {theme:"outline", size:"large", width:330, text:"continue_with", shape:"rectangular"}
                    );
                }
            };

            async function handleGoogleResponse(response) {
                const message = document.getElementById("google-login-message");
                message.style.display = "none";
                try {
                    const result = await fetch("{{ url_for('google_login') }}", {
                        method: "POST",
                        headers: {"Content-Type":"application/json"},
                        body: JSON.stringify({credential: response.credential})
                    });
                    const data = await result.json();
                    if (data.success) {
                        window.location.href = data.redirect;
                    } else {
                        message.textContent = data.message || "Google sign-in could not be completed.";
                        message.style.display = "block";
                    }
                } catch (error) {
                    message.textContent = "Google sign-in could not be completed. Please try again.";
                    message.style.display = "block";
                }
            }
        </script>

    </div>

</div>

</body>
</html>
"""


# ============================================================
# DASHBOARD PAGE
# ============================================================

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard | Stars Academy</title>
    {{ style|safe }}
</head>

<body>

<div class="navbar">

    <div class="brand">
        Stars Academy
        <small>Shalimar Branch</small>
    </div>

    <div class="nav-right">
        <span>Admin</span>
        <a href="{{ url_for('logout') }}" class="logout-btn">
            Logout
        </a>
    </div>

</div>

<div class="container">

    <h1 class="page-title">Dashboard</h1>

    <p class="subtitle">
        Academy Attendance Overview
    </p>

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="alert {{ category }}">
                {{ message }}
            </div>
        {% endfor %}
    {% endwith %}

    <!-- STATISTICS -->

    <div class="stats">

        <div class="stat-card total-card">
            <div class="stat-title">
                TOTAL STUDENTS
            </div>

            <div class="stat-number">
                {{ total_students }}
            </div>
        </div>

        <div class="stat-card present-card">
            <div class="stat-title">
                PRESENT TODAY
            </div>

            <div class="stat-number">
                {{ present }}
            </div>
        </div>

        <div class="stat-card absent-card">
            <div class="stat-title">
                ABSENT TODAY
            </div>

            <div class="stat-number">
                {{ absent }}
            </div>
        </div>

    </div>


    <div class="dashboard-grid">

        <!-- GRAPH -->

        <div class="panel">

            <h2>Attendance Graph</h2>

            <p class="subtitle">
                Today's present and absent students
            </p>

            <div class="graph">

                <div class="bar-wrapper">

                    <div class="bar-number">
                        {{ present }}
                    </div>

                    <div
                        class="bar present-bar"
                        style="height: {{ present_height }}%;"
                    ></div>

                    <div class="bar-label">
                        Present
                    </div>

                </div>


                <div class="bar-wrapper">

                    <div class="bar-number">
                        {{ absent }}
                    </div>

                    <div
                        class="bar absent-bar"
                        style="height: {{ absent_height }}%;"
                    ></div>

                    <div class="bar-label">
                        Absent
                    </div>

                </div>

            </div>

        </div>


        <!-- ATTENDANCE SUMMARY -->

        <div class="panel">

            <h2>Today's Attendance</h2>

            <p class="date-text">
                {{ today }}
            </p>

            <div class="attendance-percent">
                {{ attendance_percentage }}%
            </div>

            <p>
                Attendance Percentage
            </p>

            <div class="menu-grid">

                <a href="{{ url_for('students') }}"
                   class="menu-button">
                    Students
                </a>

                <a href="{{ url_for('attendance') }}"
                   class="menu-button">
                    Attendance
                </a>

            </div>

        </div>

    </div>

</div>

</body>
</html>
"""


# ============================================================
# STUDENTS PAGE
# ============================================================

STUDENTS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Students | Stars Academy</title>
    {{ style|safe }}
</head>

<body>

<div class="navbar">

    <div class="brand">
        Stars Academy
        <small>Shalimar Branch</small>
    </div>

    <div class="nav-right">

        <a href="{{ url_for('dashboard') }}"
           style="color:white;">
            Dashboard
        </a>

        <a href="{{ url_for('logout') }}"
           class="logout-btn">
            Logout
        </a>

    </div>

</div>


<div class="container">

    <a href="{{ url_for('dashboard') }}"
       class="back-button">
        ← Back to Dashboard
    </a>

    <h1 class="page-title">
        Students
    </h1>

    <p class="subtitle">
        Manage academy student records
    </p>


    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="alert {{ category }}">
                {{ message }}
            </div>
        {% endfor %}
    {% endwith %}


    <!-- SEARCH + CLASS DROPDOWN + ADD -->

    <form method="GET"
          action="{{ url_for('students') }}"
          class="toolbar">

        <input
            class="search-box"
            type="text"
            name="search"
            value="{{ search }}"
            placeholder="🔍 Search student by name, phone or ID..."
        >


        <select
            class="select-box"
            name="class_name"
            onchange="this.form.submit()"
        >

            <option value="All">
                All Students
            </option>

            <option value="9"
                {% if selected_class == '9' %}selected{% endif %}>
                9
            </option>

            <option value="10"
                {% if selected_class == '10' %}selected{% endif %}>
                10
            </option>

            <option value="1st Year"
                {% if selected_class == '1st Year' %}selected{% endif %}>
                1st Year
            </option>

            <option value="2nd Year"
                {% if selected_class == '2nd Year' %}selected{% endif %}>
                2nd Year
            </option>

        </select>


        <button class="gold-button" type="submit">
            Search
        </button>


        <a href="{{ url_for('add_student') }}"
           class="gold-button">
            + Add Student
        </a>

    </form>


    <!-- STUDENT TABLE -->

    <div class="student-table-wrapper">

        <table>

            <thead>

                <tr>

                    <th>ID</th>
                    <th>Student Name</th>
                    <th>Class</th>
                    <th>Phone</th>
                    <th>Fees</th>
                    <th>Attendance</th>
                    <th>Actions</th>

                </tr>

            </thead>


            <tbody>

            {% if students %}

                {% for student in students %}

                <tr>

                    <td>
                        {{ student['student_id'] }}
                    </td>

                    <td>
                        <strong>
                            {{ student['name'] }}
                        </strong>
                    </td>

                    <td>
                        {{ student['class_name'] }}
                    </td>

                    <td>
                        {{ student['phone'] }}
                    </td>

                    <td>

                        {% if student['fees'] == 'Paid' %}

                            <span class="status paid">
                                Paid
                            </span>

                        {% elif student['fees'] == 'Partially Paid' %}

                            <span class="status partial">
                                Partially Paid
                            </span>

                        {% else %}

                            <span class="status unpaid">
                                Unpaid
                            </span>

                        {% endif %}

                    </td>


                    <td>

                        {% if student['today_status'] == 'Present' %}

                            <span class="status present-status">
                                Present
                            </span>

                        {% elif student['today_status'] == 'Absent' %}

                            <span class="status absent-status">
                                Absent
                            </span>

                        {% else %}

                            <span class="status not-marked-status">
                                Not Marked
                            </span>

                        {% endif %}

                    </td>


                    <td>

                        <div class="action-buttons">

                            <a
                                href="{{ url_for('edit_student', student_id=student['id']) }}"
                                class="blue-button">
                                Edit
                            </a>


                            <form
                                method="POST"
                                action="{{ url_for('remove_student', student_id=student['id']) }}"
                                onsubmit="return confirm('Are you sure you want to remove this student? This action cannot be undone.');"
                            >

                                <button
                                    type="submit"
                                    class="red-button">
                                    Remove
                                </button>

                            </form>

                        </div>

                    </td>

                </tr>

                {% endfor %}

            {% else %}

                <tr>

                    <td colspan="7"
                        style="text-align:center;padding:30px;">

                        No students found.

                    </td>

                </tr>

            {% endif %}

            </tbody>

        </table>

    </div>

</div>

</body>
</html>
"""


# ============================================================
# ADD / EDIT STUDENT PAGE
# ============================================================

STUDENT_FORM_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ page_title }} | Stars Academy</title>
    {{ style|safe }}
</head>

<body>

<div class="navbar">

    <div class="brand">
        Stars Academy
        <small>Shalimar Branch</small>
    </div>

    <div class="nav-right">

        <a href="{{ url_for('students') }}"
           style="color:white;">
            Students
        </a>

        <a href="{{ url_for('logout') }}"
           class="logout-btn">
            Logout
        </a>

    </div>

</div>


<div class="container">

    <a href="{{ url_for('students') }}"
       class="back-button">
        ← Back to Students
    </a>


    <div class="form-card">

        <h1>{{ page_title }}</h1>

        <p class="subtitle">
            Enter the student's information below.
        </p>


        {% with messages = get_flashed_messages(with_categories=true) %}
            {% for category, message in messages %}
                <div class="alert {{ category }}">
                    {{ message }}
                </div>
            {% endfor %}
        {% endwith %}


        <form method="POST">

            <div class="form-group">

                <label>
                    Student Name
                </label>

                <input
                    type="text"
                    name="name"
                    value="{{ student['name'] if student else '' }}"
                    placeholder="Enter full name"
                    required
                >

            </div>


            <div class="form-group">

                <label>
                    Phone Number
                </label>

                <input
                    type="text"
                    name="phone"
                    value="{{ student['phone'] if student else '' }}"
                    placeholder="03XXXXXXXXX"
                    required
                >

            </div>


            <div class="form-group">

                <label>
                    Class
                </label>

                <select name="class_name" required>

                    <option value="">
                        Select Class
                    </option>

                    <option value="9"
                        {% if student and student['class_name'] == '9' %}selected{% endif %}>
                        9
                    </option>

                    <option value="10"
                        {% if student and student['class_name'] == '10' %}selected{% endif %}>
                        10
                    </option>

                    <option value="1st Year"
                        {% if student and student['class_name'] == '1st Year' %}selected{% endif %}>
                        1st Year
                    </option>

                    <option value="2nd Year"
                        {% if student and student['class_name'] == '2nd Year' %}selected{% endif %}>
                        2nd Year
                    </option>

                </select>

            </div>


            <div class="form-group">

                <label>
                    Fees
                </label>

                <select name="fees" required>

                    <option value="Paid"
                        {% if student and student['fees'] == 'Paid' %}selected{% endif %}>
                        Paid
                    </option>

                    <option value="Partially Paid"
                        {% if student and student['fees'] == 'Partially Paid' %}selected{% endif %}>
                        Partially Paid
                    </option>

                    <option value="Unpaid"
                        {% if student and student['fees'] == 'Unpaid' %}selected{% endif %}>
                        Unpaid
                    </option>

                </select>

            </div>


            <button
                class="form-submit"
                type="submit">

                {{ button_text }}

            </button>

        </form>

    </div>

</div>

</body>
</html>
"""


# ============================================================
# ATTENDANCE PAGE
# ============================================================

ATTENDANCE_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Attendance | Stars Academy</title>
    {{ style|safe }}
</head>

<body>

<div class="navbar">

    <div class="brand">
        Stars Academy
        <small>Shalimar Branch</small>
    </div>

    <div class="nav-right">

        <a href="{{ url_for('dashboard') }}"
           style="color:white;">
            Dashboard
        </a>

        <a href="{{ url_for('logout') }}"
           class="logout-btn">
            Logout
        </a>

    </div>

</div>


<div class="container">

    <a href="{{ url_for('dashboard') }}"
       class="back-button">
        ← Back to Dashboard
    </a>

    <h1 class="page-title">
        Today's Attendance
    </h1>

    <p class="subtitle">
        {{ today }}
    </p>


    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="alert {{ category }}">
                {{ message }}
            </div>
        {% endfor %}
    {% endwith %}


    <div class="student-table-wrapper">

        <table>

            <thead>

                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Class</th>
                    <th>Attendance</th>
                    <th>Action</th>
                </tr>

            </thead>


            <tbody>

            {% for student in students %}

                <tr>

                    <td>
                        {{ student['student_id'] }}
                    </td>

                    <td>
                        <strong>
                            {{ student['name'] }}
                        </strong>
                    </td>

                    <td>
                        {{ student['class_name'] }}
                    </td>


                    <td>

                        {% if student['today_status'] == 'Present' %}

                            <span class="status present-status">
                                Present
                            </span>

                        {% elif student['today_status'] == 'Absent' %}

                            <span class="status absent-status">
                                Absent
                            </span>

                        {% else %}

                            <span class="status not-marked-status">
                                Not Marked
                            </span>

                        {% endif %}

                    </td>


                    <td>

                        {% if student['today_status'] == 'Present' %}

                            <form method="POST" action="{{ url_for('mark_attendance', student_id=student['id']) }}">
                                <input type="hidden" name="status" value="Absent">
                                <button class="red-button" type="submit">Mark Absent</button>
                            </form>

                        {% elif student['today_status'] == 'Absent' %}

                            <form method="POST" action="{{ url_for('mark_attendance', student_id=student['id']) }}">
                                <input type="hidden" name="status" value="Present">
                                <button class="green-button" type="submit">Mark Present</button>
                            </form>

                        {% else %}

                            <div class="action-buttons">
                                <form method="POST" action="{{ url_for('mark_attendance', student_id=student['id']) }}">
                                    <input type="hidden" name="status" value="Present">
                                    <button class="green-button" type="submit">Mark Present</button>
                                </form>
                                <form method="POST" action="{{ url_for('mark_attendance', student_id=student['id']) }}">
                                    <input type="hidden" name="status" value="Absent">
                                    <button class="red-button" type="submit">Mark Absent</button>
                                </form>
                            </div>

                        {% endif %}

                    </td>

                </tr>

            {% endfor %}

            </tbody>

        </table>

    </div>

</div>

</body>
</html>
"""


# ============================================================
# LOGIN
# ============================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()

        admin = db.execute(
            "SELECT * FROM admins WHERE username = ?",
            (username,)
        ).fetchone()

        db.close()

        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]

            return redirect(url_for("dashboard"))

        flash(
            "Incorrect username or password.",
            "error"
        )

    return render_template_string(
        LOGIN_PAGE,
        style=BASE_STYLE,
        google_client_id=GOOGLE_CLIENT_ID
    )


# ============================================================
# GOOGLE SIGN-IN
# ============================================================

@app.route("/google-login", methods=["POST"])
def google_login():
    data = request.get_json(silent=True) or {}
    credential = data.get("credential", "")

    if not credential:
        return {"success": False, "message": "Google credential was not received."}, 400

    try:
        idinfo = id_token.verify_oauth2_token(
            credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        if not idinfo.get("email_verified"):
            return {"success": False, "message": "Your Google email is not verified."}, 403

        google_email = idinfo.get("email", "").strip().lower()
        allowed_email = GOOGLE_ALLOWED_EMAIL.strip().lower()

        if not allowed_email or allowed_email == "your_google_email_here":
            return {"success": False, "message": "Google sign-in is not configured for an authorized academy email yet."}, 403

        if google_email != allowed_email:
            return {"success": False, "message": "This Google account is not authorized for the academy dashboard."}, 403

        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        db.close()

        if not admin:
            return {"success": False, "message": "The academy admin account was not found."}, 500

        session["admin_id"] = admin["id"]
        session["username"] = admin["username"]
        session["google_email"] = google_email
        return {"success": True, "redirect": url_for("dashboard")}

    except ValueError:
        return {"success": False, "message": "Google sign-in verification failed."}, 401
    except Exception:
        return {"success": False, "message": "Google sign-in could not be completed."}, 500


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    db = get_db()

    total_students = db.execute(
        "SELECT COUNT(*) AS total FROM students"
    ).fetchone()["total"]

    today = date.today().isoformat()

    present = db.execute("""
        SELECT COUNT(*) AS total
        FROM students s
        JOIN attendance a
        ON s.id = a.student_id
        WHERE a.attendance_date = ?
        AND a.status = 'Present'
    """, (today,)).fetchone()["total"]

    absent = db.execute("""
        SELECT COUNT(*) AS total
        FROM students s
        JOIN attendance a
        ON s.id = a.student_id
        WHERE a.attendance_date = ?
        AND a.status = 'Absent'
    """, (today,)).fetchone()["total"]

    db.close()

    # If attendance hasn't been marked yet,
    # the dashboard starts with zero.
    if total_students > 0:

        attendance_percentage = round(
            (present / total_students) * 100
        )

    else:

        attendance_percentage = 0

    # Graph heights
    if total_students > 0:

        present_height = max(
            5,
            (present / total_students) * 100
        )

        absent_height = max(
            5,
            (absent / total_students) * 100
        )

    else:

        present_height = 5
        absent_height = 5

    return render_template_string(
        DASHBOARD_PAGE,
        style=BASE_STYLE,
        total_students=total_students,
        present=present,
        absent=absent,
        attendance_percentage=attendance_percentage,
        present_height=present_height,
        absent_height=absent_height,
        today=today
    )


# ============================================================
# STUDENTS
# ============================================================

@app.route("/students")
@login_required
def students():

    search = request.args.get(
        "search",
        ""
    ).strip()

    selected_class = request.args.get(
        "class_name",
        "All"
    )

    today = date.today().isoformat()

    db = get_db()

    query = """
        SELECT
            s.*,
            a.status AS today_status

        FROM students s

        LEFT JOIN attendance a
        ON s.id = a.student_id
        AND a.attendance_date = ?

        WHERE 1=1
    """

    parameters = [today]


    # Class filter
    if selected_class != "All":

        query += """
            AND s.class_name = ?
        """

        parameters.append(
            selected_class
        )


    # Search
    if search:

        query += """
            AND (
                s.name LIKE ?
                OR s.phone LIKE ?
                OR s.student_id LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend([
            search_value,
            search_value,
            search_value
        ])


    query += """
        ORDER BY s.name ASC
    """


    students_list = db.execute(
        query,
        parameters
    ).fetchall()

    db.close()


    return render_template_string(
        STUDENTS_PAGE,
        style=BASE_STYLE,
        students=students_list,
        search=search,
        selected_class=selected_class
    )


# ============================================================
# ADD STUDENT
# ============================================================

@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        class_name = request.form.get(
            "class_name",
            ""
        ).strip()

        fees = request.form.get(
            "fees",
            "Unpaid"
        )


        if not name or not phone or not class_name:

            flash(
                "Please complete all required fields.",
                "error"
            )

            return redirect(
                url_for("add_student")
            )


        db = get_db()

        # Create automatic student ID
        next_number = db.execute(
            "SELECT COUNT(*) + 1 AS number FROM students"
        ).fetchone()["number"]

        student_id = f"STU-{next_number:04d}"


        # Make sure ID is unique
        while db.execute(
            "SELECT id FROM students WHERE student_id = ?",
            (student_id,)
        ).fetchone():

            next_number += 1
            student_id = f"STU-{next_number:04d}"


        db.execute("""
            INSERT INTO students
            (
                student_id,
                name,
                phone,
                class_name,
                fees
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            student_id,
            name,
            phone,
            class_name,
            fees
        ))


        db.commit()
        db.close()


        flash(
            f"Student added successfully. ID: {student_id}",
            "success"
        )

        return redirect(
            url_for("students")
        )


    return render_template_string(
        STUDENT_FORM_PAGE,
        style=BASE_STYLE,
        page_title="Add Student",
        button_text="SAVE STUDENT",
        student=None
    )


# ============================================================
# EDIT STUDENT
# ============================================================

@app.route(
    "/students/edit/<int:student_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_student(student_id):

    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()


    if not student:

        db.close()

        flash(
            "Student not found.",
            "error"
        )

        return redirect(
            url_for("students")
        )


    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        class_name = request.form.get(
            "class_name",
            ""
        ).strip()

        fees = request.form.get(
            "fees",
            "Unpaid"
        )


        if not name or not phone or not class_name:

            flash(
                "Please complete all required fields.",
                "error"
            )

            db.close()

            return redirect(
                url_for(
                    "edit_student",
                    student_id=student_id
                )
            )


        db.execute("""
            UPDATE students

            SET
                name = ?,
                phone = ?,
                class_name = ?,
                fees = ?

            WHERE id = ?
        """, (
            name,
            phone,
            class_name,
            fees,
            student_id
        ))


        db.commit()
        db.close()


        flash(
            "Student information updated successfully.",
            "success"
        )

        return redirect(
            url_for("students")
        )


    db.close()


    return render_template_string(
        STUDENT_FORM_PAGE,
        style=BASE_STYLE,
        page_title="Edit Student",
        button_text="UPDATE STUDENT",
        student=student
    )


# ============================================================
# REMOVE STUDENT
# ============================================================

@app.route(
    "/students/remove/<int:student_id>",
    methods=["POST"]
)
@login_required
def remove_student(student_id):

    db = get_db()

    student = db.execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()


    if student:

        # Remove attendance records first
        db.execute(
            "DELETE FROM attendance WHERE student_id = ?",
            (student_id,)
        )

        # Remove student
        db.execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )

        db.commit()

        flash(
            "Student record removed successfully.",
            "success"
        )

    else:

        flash(
            "Student not found.",
            "error"
        )


    db.close()

    return redirect(
        url_for("students")
    )


# ============================================================
# ATTENDANCE PAGE
# ============================================================

@app.route("/attendance")
@login_required
def attendance():

    today = date.today().isoformat()

    db = get_db()

    students_list = db.execute("""
        SELECT
            s.*,
            a.status AS today_status

        FROM students s

        LEFT JOIN attendance a
        ON s.id = a.student_id
        AND a.attendance_date = ?

        ORDER BY s.class_name, s.name
    """, (today,)).fetchall()

    db.close()


    return render_template_string(
        ATTENDANCE_PAGE,
        style=BASE_STYLE,
        students=students_list,
        today=today
    )


# ============================================================
# MARK ATTENDANCE
# ============================================================

@app.route(
    "/attendance/<int:student_id>",
    methods=["POST"]
)
@login_required
def mark_attendance(student_id):

    status = request.form.get(
        "status",
        "Absent"
    )

    if status not in ["Present", "Absent"]:

        flash(
            "Invalid attendance status.",
            "error"
        )

        return redirect(
            url_for("attendance")
        )


    today = date.today().isoformat()

    db = get_db()


    existing = db.execute("""
        SELECT id
        FROM attendance

        WHERE student_id = ?
        AND attendance_date = ?
    """, (
        student_id,
        today
    )).fetchone()


    if existing:

        db.execute("""
            UPDATE attendance

            SET status = ?

            WHERE student_id = ?
            AND attendance_date = ?
        """, (
            status,
            student_id,
            today
        ))

    else:

        db.execute("""
            INSERT INTO attendance
            (
                student_id,
                attendance_date,
                status
            )

            VALUES (?, ?, ?)
        """, (
            student_id,
            today,
            status
        ))


    db.commit()
    db.close()


    return redirect(
        url_for("attendance")
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


# ============================================================
# START APPLICATION
# ============================================================

if __name__ == "__main__":

    init_database()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )