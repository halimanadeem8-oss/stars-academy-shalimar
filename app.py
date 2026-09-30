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

import os

# Secret key: set SECRET_KEY in Render for production.
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "dev-only-change-this-secret-key"
)

DATABASE = os.environ.get("DATABASE_PATH", "academy.db")

# Default username/password login.
# For production, set ADMIN_USERNAME and ADMIN_PASSWORD in Render.
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# Google Sign-In
# Any Google account with a verified email may sign in.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

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

    # Admissions table
    db.execute("""
        CREATE TABLE IF NOT EXISTS admissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            dob TEXT NOT NULL,
            gender TEXT NOT NULL,
            class_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            address TEXT NOT NULL,
            previous_school TEXT,
            admission_date TEXT NOT NULL,
            submitted_at TEXT NOT NULL
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
# FRONTEND / HTML
# NOTE: This section contains ONLY presentation/navigation.
# Existing Flask routes, database logic and authentication below
# are intentionally preserved.
# ============================================================

BASE_STYLE = """
<style>
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,Arial,Helvetica,sans-serif;background:#f4f7fb;color:#172033}
a{text-decoration:none;color:inherit}
button,input,select{font:inherit}
.navbar{height:72px;background:#101b3d;color:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 28px;box-shadow:0 4px 18px rgba(16,27,61,.16);position:sticky;top:0;z-index:100}
.brand{font-size:21px;font-weight:800;letter-spacing:.2px}.brand small{display:block;font-size:11px;font-weight:500;color:#d9b85c;margin-top:3px}
.nav-right{display:flex;align-items:center;gap:14px}.nav-link{color:#fff;font-weight:700;font-size:14px}.logout-btn{background:#c9a54a;color:#101b3d;padding:9px 15px;border-radius:9px;font-weight:800}
.menu-btn{border:0;background:transparent;color:#fff;font-size:28px;cursor:pointer;padding:4px 8px;line-height:1}
.side-menu{position:fixed;top:0;left:-310px;width:290px;height:100vh;background:#101b3d;color:#fff;z-index:1000;transition:left .25s ease;padding:26px 20px;box-shadow:10px 0 30px rgba(0,0,0,.2)}
.side-menu.open{left:0}.side-menu h2{margin:0 0 4px;font-size:22px}.side-menu p{margin:0 0 22px;color:#d9b85c;font-size:12px}
.side-menu a{display:block;padding:13px 14px;margin:4px 0;border-radius:9px;color:#fff;font-weight:700}.side-menu a:hover{background:rgba(255,255,255,.09)}
.close-menu{position:absolute;right:16px;top:12px;border:0;background:none;color:#fff;font-size:26px;cursor:pointer}
.menu-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.38);z-index:999}.menu-overlay.open{display:block}
.container{max-width:1180px;margin:0 auto;padding:34px 22px 60px}
.page-title{font-size:32px;margin:0 0 6px;color:#101b3d}.subtitle{color:#687386;margin:0 0 22px}
.hero{background:linear-gradient(135deg,#101b3d,#1a2b5d);color:#fff;border-radius:20px;padding:42px;margin-bottom:24px;box-shadow:0 14px 35px rgba(16,27,61,.16)}
.hero h1{font-size:38px;margin:0 0 8px}.hero p{max-width:700px;color:#dce3f2;line-height:1.7;margin:0}
.hero-badge{display:inline-block;background:#d9b85c;color:#101b3d;font-weight:800;padding:7px 12px;border-radius:20px;margin-bottom:14px;font-size:12px}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:22px 0}.stat-card,.panel,.info-card{background:#fff;border-radius:16px;padding:22px;box-shadow:0 5px 22px rgba(20,34,65,.07);border:1px solid #e8edf5}
.stat-title{font-size:12px;font-weight:800;color:#687386}.stat-number{font-size:34px;font-weight:900;color:#101b3d;margin-top:8px}
.dashboard-grid{display:grid;grid-template-columns:1.4fr 1fr;gap:20px}.panel h2{margin:0 0 7px;color:#101b3d}.date-text{color:#687386}
.graph{height:230px;display:flex;align-items:flex-end;justify-content:center;gap:60px;padding-top:25px}.bar-wrapper{height:190px;width:70px;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}.bar{width:52px;border-radius:9px 9px 0 0;min-height:5px}.present-bar{background:#2e8b67}.absent-bar{background:#c95656}.bar-number{font-weight:800;margin-bottom:6px}.bar-label{font-size:13px;margin-top:8px;color:#687386}
.attendance-percent{font-size:52px;font-weight:900;color:#c09a3e;margin-top:18px}.menu-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:20px}
.menu-button,.gold-button,.green-button,.red-button,.form-submit{display:inline-block;border:0;cursor:pointer;border-radius:9px;padding:11px 15px;font-weight:800}.menu-button,.gold-button,.form-submit{background:#c9a54a;color:#101b3d}.green-button{background:#dff4e9;color:#176344}.red-button{background:#fde4e4;color:#9c2e2e}
.section{margin-top:26px}.section h2{color:#101b3d;margin-bottom:8px}.info-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.info-card h3{margin-top:0;color:#101b3d}.info-card p{color:#687386;line-height:1.65}
.principal-card{display:flex;gap:25px;align-items:center;background:#fff;border:1px solid #e8edf5;border-radius:16px;padding:24px;box-shadow:0 5px 22px rgba(20,34,65,.07)}.principal-photo{width:135px;height:135px;border-radius:50%;object-fit:cover;background:#e9edf5;display:flex;align-items:center;justify-content:center;color:#687386;font-size:12px;text-align:center}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}.search-box,.select-box,input,select{border:1px solid #dbe2ec;border-radius:9px;padding:11px 12px;background:#fff;outline:none}.search-box{min-width:290px;flex:1}
.student-table-wrapper{background:#fff;border:1px solid #e8edf5;border-radius:15px;overflow:auto;box-shadow:0 5px 22px rgba(20,34,65,.06)}table{width:100%;border-collapse:collapse;min-width:780px}th,td{padding:14px 15px;text-align:left;border-bottom:1px solid #edf0f5}th{background:#f8f9fc;color:#687386;font-size:12px;text-transform:uppercase}td{font-size:14px}.action-buttons{display:flex;gap:7px;flex-wrap:wrap}
.status{display:inline-block;padding:5px 9px;border-radius:20px;font-size:12px;font-weight:800}.paid,.present-status{background:#dff4e9;color:#176344}.partial,.not-marked-status{background:#fff2cf;color:#8a6a17}.unpaid,.absent-status{background:#fde4e4;color:#9c2e2e}
.form-card{max-width:650px;background:#fff;border:1px solid #e8edf5;border-radius:16px;padding:28px;box-shadow:0 5px 22px rgba(20,34,65,.07)}.form-group{margin-bottom:17px}.form-group label{display:block;font-weight:800;margin-bottom:7px}.form-group input,.form-group select{width:100%}.form-submit{width:100%;margin-top:8px}.admission-card{max-width:900px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.form-group.full{grid-column:1 / -1}.required-star{color:#b43a36}.success-box{background:#dff4e9;color:#176344;border:1px solid #b9e3cc;padding:16px;border-radius:12px;margin-bottom:20px;font-weight:700}.success-box span{display:block;font-weight:500;margin-top:5px}.form-help{font-size:12px;color:#7a8494;margin-top:5px}@media(max-width:700px){.form-grid{grid-template-columns:1fr}.form-group.full{grid-column:auto}}.back-button{display:inline-block;margin-bottom:18px;color:#6d5721;font-weight:800}
.alert{padding:11px 14px;border-radius:9px;margin:12px 0}.alert.error{background:#fde4e4;color:#9c2e2e}.alert.success{background:#dff4e9;color:#176344}
.login-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:25px;background:linear-gradient(135deg,#101b3d,#1c315f)}.login-box{width:min(430px,100%);background:#fff;border-radius:20px;padding:34px;box-shadow:0 18px 55px rgba(0,0,0,.22)}.login-title{text-align:center;color:#101b3d;margin:0}.login-subtitle{text-align:center;color:#687386;line-height:1.6;margin:7px 0 25px}.login-box .form-group input{width:100%}.login-button{width:100%;border:0;border-radius:9px;background:#c9a54a;color:#101b3d;padding:12px;font-weight:900;cursor:pointer}
.footer{margin-top:35px;padding:25px;text-align:center;color:#7a8494;font-size:13px}
@media(max-width:800px){.stats,.info-grid,.dashboard-grid{grid-template-columns:1fr}.navbar{padding:0 15px}.nav-right>span,.nav-link{display:none}.hero{padding:28px}.hero h1{font-size:29px}.principal-card{flex-direction:column;text-align:center}.search-box{min-width:100%}}
</style>
"""

NAV_HTML = """
<div class="navbar">
    <div style="display:flex;align-items:center;gap:12px;">
        <button class="menu-btn" type="button" onclick="openMenu()" aria-label="Open menu">☰</button>
        <a href="/dashboard" class="brand">Stars Academy<small>Shalimar Branch</small></a>
    </div>
    <div class="nav-right">
        <span>Admin</span>
        <a href="/logout" class="logout-btn">Logout</a>
    </div>
</div>
<div id="menuOverlay" class="menu-overlay" onclick="closeMenu()"></div>
<aside id="sideMenu" class="side-menu">
    <button class="close-menu" type="button" onclick="closeMenu()">×</button>
    <h2>Stars Academy</h2><p>Shalimar Branch</p>
    <a href="/dashboard">⌂ Home</a>
    <a href="/students">👨‍🎓 Students</a>
    <a href="/attendance">✓ Attendance</a>
    <a href="/admissions">▣ Admissions</a>
    <a href="/dashboard#faculty">♙ Faculty</a>
    <a href="/dashboard#announcements">▣ Announcements</a>
    <a href="/dashboard#about">ⓘ About Academy</a>
    <a href="/dashboard#contact">☎ Contact</a>
    <a href="/logout">↪ Logout</a>
</aside>
<script>
function openMenu(){document.getElementById('sideMenu').classList.add('open');document.getElementById('menuOverlay').classList.add('open')}
function closeMenu(){document.getElementById('sideMenu').classList.remove('open');document.getElementById('menuOverlay').classList.remove('open')}
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenu()})
</script>
"""

LOGIN_PAGE = """
<!DOCTYPE html><html><head><title>Stars Academy | Login</title>{{ style|safe }}</head>
<body>
<div class="login-page"><div class="login-box">
<h1 class="login-title">Stars Academy</h1>
<p class="login-subtitle"><strong>Shalimar Branch</strong><br>Academy Management System</p>
{% with messages=get_flashed_messages(with_categories=true) %}
{% for category,message in messages %}<div class="alert {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<form method="POST" action="{{ url_for('login') }}" autocomplete="on">
<div class="form-group"><label for="username">Username</label><input id="username" type="text" name="username" placeholder="Enter username" required autocomplete="username"></div>
<div class="form-group"><label for="password">Password</label><input id="password" type="password" name="password" placeholder="Enter password" required autocomplete="current-password"></div>
<button class="login-button" type="submit">LOGIN</button>
</form>
<div style="display:flex;align-items:center;gap:10px;margin:24px 0 18px"><div style="height:1px;background:#e1e5ec;flex:1"></div><span style="color:#697386;font-size:13px">OR</span><div style="height:1px;background:#e1e5ec;flex:1"></div></div>
<div id="google-login-button" style="display:flex;justify-content:center"></div>
<p id="google-login-message" style="display:none;text-align:center;color:#b43a36;font-size:13px;margin-top:12px"></p>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script>
function setupGoogle(){
    if(!window.google || !google.accounts || !google.accounts.id) return;
    const clientId={{ google_client_id|tojson }};
    if(!clientId) return;
    google.accounts.id.initialize({client_id:clientId,callback:handleGoogleResponse});
    google.accounts.id.renderButton(document.getElementById("google-login-button"),
        {theme:"outline",size:"large",width:330,text:"continue_with",shape:"rectangular"});
}
window.addEventListener("load",setupGoogle);
setTimeout(setupGoogle,1500);
async function handleGoogleResponse(response){
    const message=document.getElementById("google-login-message");
    message.style.display="none";
    try{
        const result=await fetch("{{ url_for('google_login') }}",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({credential:response.credential})});
        const data=await result.json();
        if(data.success){window.location.href=data.redirect;return;}
        message.textContent=data.message||"Google sign-in could not be completed.";
        message.style.display="block";
    }catch(error){
        message.textContent="Google sign-in could not be completed. Please try again.";
        message.style.display="block";
    }
}
</script>
</div></div></body></html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html><html><head><title>Home | Stars Academy</title>{{ style|safe }}</head><body>
{{ nav|safe }}
<div class="container">
<section class="hero" id="home">
<span class="hero-badge">SHALIMAR BRANCH</span><h1>Welcome to Stars Academy</h1>
<p>A professional academy management dashboard for student records, attendance and academy information.</p>
</section>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="alert {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<div class="stats">
<div class="stat-card"><div class="stat-title">TOTAL STUDENTS</div><div class="stat-number">{{ total_students }}</div></div>
<div class="stat-card"><div class="stat-title">PRESENT TODAY</div><div class="stat-number">{{ present }}</div></div>
<div class="stat-card"><div class="stat-title">ABSENT TODAY</div><div class="stat-number">{{ absent }}</div></div>
</div>
<div class="dashboard-grid">
<div class="panel"><h2>Attendance Overview</h2><p class="subtitle">Today's attendance at a glance</p>
<div class="graph"><div class="bar-wrapper"><div class="bar-number">{{ present }}</div><div class="bar present-bar" style="height:{{ present_height }}%"></div><div class="bar-label">Present</div></div>
<div class="bar-wrapper"><div class="bar-number">{{ absent }}</div><div class="bar absent-bar" style="height:{{ absent_height }}%"></div><div class="bar-label">Absent</div></div></div></div>
<div class="panel"><h2>Quick Access</h2><p class="date-text">{{ today }}</p><div class="attendance-percent">{{ attendance_percentage }}%</div><p>Attendance Percentage</p>
<div class="menu-grid"><a href="{{ url_for('students') }}" class="menu-button">Students</a><a href="{{ url_for('attendance') }}" class="menu-button">Attendance</a></div></div>
</div>

<section class="section" id="admissions"><h2>Admissions</h2><div class="info-card"><h3>New Student Admissions</h3><p>Use the Students section to add a new student record and keep academy information organized.</p><a href="{{ url_for('add_student') }}" class="gold-button">Add Student</a></div></section>

<section class="section" id="faculty"><h2>Faculty</h2><div class="info-grid"><div class="info-card"><h3>Dedicated Teachers</h3><p>Our faculty section can be used to present the academy's teaching team and academic support.</p></div><div class="info-card"><h3>Academic Guidance</h3><p>Students receive structured guidance focused on learning, practice and progress.</p></div><div class="info-card"><h3>Student Support</h3><p>The academy aims to maintain a supportive and organized learning environment.</p></div></div></section>

<section class="section" id="announcements"><h2>Announcements</h2><div class="info-card"><h3>Academy Updates</h3><p>Important academy announcements, class updates and notices can be displayed here.</p></div></section>

<section class="section" id="about"><h2>About Stars Academy</h2><div class="info-card"><p>Stars Academy — Shalimar Branch is presented as a modern, organized learning environment with student management and attendance tools.</p></div></section>

<section class="section" id="principal"><h2>Principal's Message</h2><div class="principal-card"><img class="principal-photo" src="data:image/jpeg;base64,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" alt="Principal Halima"><div><h3 style="margin:0;color:#101b3d">Principal Halima</h3><p style="color:#687386;line-height:1.7">“Our aim is to provide students with a focused, respectful and encouraging environment where every student can grow.”</p></div></div></section>

<section class="section" id="contact"><h2>Contact</h2><div class="info-grid"><div class="info-card"><h3>Branch</h3><p>Stars Academy<br>Shalimar Branch</p></div><div class="info-card"><h3>Office</h3><p>For admissions and academy information, contact the branch office.</p></div><div class="info-card"><h3>Management</h3><p>Academy management can use this dashboard to maintain student records and attendance.</p></div></div></section>
<div class="footer">© Stars Academy | Shalimar Branch</div>
</div></body></html>
"""

STUDENTS_PAGE = """
<!DOCTYPE html><html><head><title>Students | Stars Academy</title>{{ style|safe }}</head><body>
{{ nav|safe }}<div class="container">
<a href="{{ url_for('dashboard') }}" class="back-button">← Back to Home</a>
<h1 class="page-title">Students</h1><p class="subtitle">Manage academy student records.</p>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="alert {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<form method="GET" action="{{ url_for('students') }}" class="toolbar">
<input class="search-box" type="text" name="search" value="{{ search }}" placeholder="Search by name, phone or ID">
<select class="select-box" name="class_name" onchange="this.form.submit()"><option value="All">All Students</option><option value="9" {% if selected_class=='9' %}selected{% endif %}>9</option><option value="10" {% if selected_class=='10' %}selected{% endif %}>10</option><option value="1st Year" {% if selected_class=='1st Year' %}selected{% endif %}>1st Year</option><option value="2nd Year" {% if selected_class=='2nd Year' %}selected{% endif %}>2nd Year</option></select>
<button class="gold-button" type="submit">Search</button><a href="{{ url_for('add_student') }}" class="gold-button">+ Add Student</a></form>
<div class="student-table-wrapper"><table><thead><tr><th>ID</th><th>Student</th><th>Class</th><th>Phone</th><th>Fees</th><th>Attendance</th><th>Actions</th></tr></thead><tbody>
{% for student in students %}<tr><td>{{ student['student_id'] }}</td><td><strong>{{ student['name'] }}</strong></td><td>{{ student['class_name'] }}</td><td>{{ student['phone'] }}</td><td>{% if student['fees']=='Paid' %}<span class="status paid">Paid</span>{% elif student['fees']=='Partially Paid' %}<span class="status partial">Partially Paid</span>{% else %}<span class="status unpaid">Unpaid</span>{% endif %}</td><td>{% if student['today_status']=='Present' %}<span class="status present-status">Present</span>{% elif student['today_status']=='Absent' %}<span class="status absent-status">Absent</span>{% else %}<span class="status not-marked-status">Not Marked</span>{% endif %}</td>
<td><div class="action-buttons"><a href="{{ url_for('edit_student',student_id=student['id']) }}" class="gold-button">Edit</a><form method="POST" action="{{ url_for('remove_student',student_id=student['id']) }}" onsubmit="return confirm('Remove this student?')"><button class="red-button" type="submit">Remove</button></form></div></td></tr>
{% else %}<tr><td colspan="7" style="text-align:center;padding:35px;color:#687386">No students found.</td></tr>{% endfor %}
</tbody></table></div></div></body></html>
"""

STUDENT_FORM_PAGE = """
<!DOCTYPE html><html><head><title>{{ page_title }} | Stars Academy</title>{{ style|safe }}</head><body>
{{ nav|safe }}<div class="container"><a href="{{ url_for('students') }}" class="back-button">← Back to Students</a>
<div class="form-card"><h1 class="page-title">{{ page_title }}</h1><p class="subtitle">Enter the student's information below.</p>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="alert {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<form method="POST"><div class="form-group"><label>Student Name</label><input type="text" name="name" value="{{ student['name'] if student else '' }}" required></div>
<div class="form-group"><label>Phone Number</label><input type="text" name="phone" value="{{ student['phone'] if student else '' }}" required></div>
<div class="form-group"><label>Class</label><select name="class_name" required><option value="">Select Class</option><option value="9" {% if student and student['class_name']=='9' %}selected{% endif %}>9</option><option value="10" {% if student and student['class_name']=='10' %}selected{% endif %}>10</option><option value="1st Year" {% if student and student['class_name']=='1st Year' %}selected{% endif %}>1st Year</option><option value="2nd Year" {% if student and student['class_name']=='2nd Year' %}selected{% endif %}>2nd Year</option></select></div>
<div class="form-group"><label>Fees</label><select name="fees" required><option value="Paid" {% if student and student['fees']=='Paid' %}selected{% endif %}>Paid</option><option value="Partially Paid" {% if student and student['fees']=='Partially Paid' %}selected{% endif %}>Partially Paid</option><option value="Unpaid" {% if not student or student['fees']=='Unpaid' %}selected{% endif %}>Unpaid</option></select></div>
<button class="form-submit" type="submit">{{ button_text }}</button></form></div></div></body></html>
"""

ATTENDANCE_PAGE = """
<!DOCTYPE html><html><head><title>Attendance | Stars Academy</title>{{ style|safe }}</head><body>
{{ nav|safe }}<div class="container"><a href="{{ url_for('dashboard') }}" class="back-button">← Back to Home</a>
<h1 class="page-title">Today's Attendance</h1><p class="subtitle">{{ today }}</p>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="alert {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
<div class="student-table-wrapper"><table><thead><tr><th>Student ID</th><th>Name</th><th>Class</th><th>Attendance</th><th>Action</th></tr></thead><tbody>
{% for student in students %}<tr><td>{{ student['student_id'] }}</td><td><strong>{{ student['name'] }}</strong></td><td>{{ student['class_name'] }}</td><td>{% if student['today_status']=='Present' %}<span class="status present-status">Present</span>{% elif student['today_status']=='Absent' %}<span class="status absent-status">Absent</span>{% else %}<span class="status not-marked-status">Not Marked</span>{% endif %}</td><td>
{% if student['today_status']=='Present' %}<form method="POST" action="{{ url_for('mark_attendance',student_id=student['id']) }}"><input type="hidden" name="status" value="Absent"><button class="red-button">Mark Absent</button></form>
{% elif student['today_status']=='Absent' %}<form method="POST" action="{{ url_for('mark_attendance',student_id=student['id']) }}"><input type="hidden" name="status" value="Present"><button class="green-button">Mark Present</button></form>
{% else %}<div class="action-buttons"><form method="POST" action="{{ url_for('mark_attendance',student_id=student['id']) }}"><input type="hidden" name="status" value="Present"><button class="green-button">Mark Present</button></form><form method="POST" action="{{ url_for('mark_attendance',student_id=student['id']) }}"><input type="hidden" name="status" value="Absent"><button class="red-button">Mark Absent</button></form></div>{% endif %}
</td></tr>{% else %}<tr><td colspan="5" style="text-align:center;padding:35px;color:#687386">No students have been added yet.</td></tr>{% endfor %}
</tbody></table></div></div></body></html>
"""


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

        if not google_email:
            return {"success": False, "message": "Google did not provide an email address."}, 403

        # IMPORTANT: There is intentionally NO allowed-email check here.
        # Any Google account with a verified email can sign in.
        db = get_db()
        admin = db.execute("SELECT * FROM admins WHERE username = ?", (ADMIN_USERNAME,)).fetchone()
        db.close()

        if not admin:
            return {"success": False, "message": "The academy admin account was not found."}, 500

        session["admin_id"] = admin["id"]
        session["username"] = admin["username"]
        session["google_email"] = google_email
        return {"success": True, "redirect": url_for("dashboard")}

    except Exception as e:
        return {"success": False, "message": f"Google sign-in error: {str(e)}"}, 500


# ============================================================
# ADMISSIONS PAGE
# ============================================================

ADMISSIONS_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stars Academy | Admissions</title>
    {{ style|safe }}
</head>
<body>
{{ nav|safe }}

<div class="container">
    <a href="/dashboard" class="back-button">← Back to Home</a>

    <div class="hero">
        <span class="hero-badge">ADMISSIONS</span>
        <h1>Admission Application</h1>
        <p>Fill in the form below to submit a new student admission application to Stars Academy, Shalimar Branch.</p>
    </div>

    {% if submitted %}
    <div class="success-box">
        ✓ Admission application submitted successfully!
        <span>Application for <strong>{{ student_name }}</strong> has been received by Stars Academy.</span>
    </div>
    {% endif %}

    {% with messages=get_flashed_messages(with_categories=true) %}
        {% for category,message in messages %}
            <div class="alert {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endwith %}

    <div class="form-card admission-card">
        <h2 style="margin-top:0;color:#101b3d">Student Information</h2>
        <p class="subtitle">Please provide accurate information. Fields marked with <span class="required-star">*</span> are required.</p>

        <form method="POST" action="/admissions" autocomplete="on">
            <div class="form-grid">
                <div class="form-group">
                    <label for="student_name">Student Full Name <span class="required-star">*</span></label>
                    <input id="student_name" name="student_name" type="text" placeholder="Enter student's full name" value="{{ form_data.get('student_name','') }}" required>
                </div>

                <div class="form-group">
                    <label for="guardian_name">Father / Guardian Name <span class="required-star">*</span></label>
                    <input id="guardian_name" name="guardian_name" type="text" placeholder="Enter father or guardian name" value="{{ form_data.get('guardian_name','') }}" required>
                </div>

                <div class="form-group">
                    <label for="dob">Date of Birth <span class="required-star">*</span></label>
                    <input id="dob" name="dob" type="date" value="{{ form_data.get('dob','') }}" required>
                </div>

                <div class="form-group">
                    <label for="gender">Gender <span class="required-star">*</span></label>
                    <select id="gender" name="gender" required>
                        <option value="">Select gender</option>
                        <option value="Male" {% if form_data.get('gender') == 'Male' %}selected{% endif %}>Male</option>
                        <option value="Female" {% if form_data.get('gender') == 'Female' %}selected{% endif %}>Female</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="class_name">Class Applying For <span class="required-star">*</span></label>
                    <select id="class_name" name="class_name" required>
                        <option value="">Select class</option>
                        {% for class_option in ['Playgroup','Nursery','Prep','1','2','3','4','5','6','7','8','9','10'] %}
                        <option value="{{ class_option }}" {% if form_data.get('class_name') == class_option %}selected{% endif %}>Class {{ class_option }}</option>
                        {% endfor %}
                    </select>
                </div>

                <div class="form-group">
                    <label for="phone">Phone Number <span class="required-star">*</span></label>
                    <input id="phone" name="phone" type="tel" placeholder="03XX-XXXXXXX" value="{{ form_data.get('phone','') }}" required>
                </div>

                <div class="form-group">
                    <label for="email">Email Address</label>
                    <input id="email" name="email" type="email" placeholder="example@email.com" value="{{ form_data.get('email','') }}">
                </div>

                <div class="form-group">
                    <label for="admission_date">Preferred Admission Date <span class="required-star">*</span></label>
                    <input id="admission_date" name="admission_date" type="date" value="{{ form_data.get('admission_date', today) }}" required>
                </div>

                <div class="form-group full">
                    <label for="previous_school">Previous School</label>
                    <input id="previous_school" name="previous_school" type="text" placeholder="Enter previous school name (if applicable)" value="{{ form_data.get('previous_school','') }}">
                </div>

                <div class="form-group full">
                    <label for="address">Home Address <span class="required-star">*</span></label>
                    <input id="address" name="address" type="text" placeholder="Enter complete home address" value="{{ form_data.get('address','') }}" required>
                </div>
            </div>

            <p class="form-help">By submitting this form, the admission information will be saved in the academy's admission records.</p>
            <button class="form-submit" type="submit">Submit Admission Application</button>
        </form>
    </div>

    <div class="footer">Stars Academy | Shalimar Branch • Admissions</div>
</div>
</body>
</html>
"""


# ============================================================
# ADMISSIONS
# ============================================================

@app.route("/admissions", methods=["GET", "POST"])
@login_required
def admissions():

    form_data = {}
    submitted = False

    if request.method == "POST":
        form_data = {
            "student_name": request.form.get("student_name", "").strip(),
            "guardian_name": request.form.get("guardian_name", "").strip(),
            "dob": request.form.get("dob", "").strip(),
            "gender": request.form.get("gender", "").strip(),
            "class_name": request.form.get("class_name", "").strip(),
            "phone": request.form.get("phone", "").strip(),
            "email": request.form.get("email", "").strip(),
            "address": request.form.get("address", "").strip(),
            "previous_school": request.form.get("previous_school", "").strip(),
            "admission_date": request.form.get("admission_date", "").strip(),
        }

        required_fields = [
            "student_name", "guardian_name", "dob", "gender",
            "class_name", "phone", "address", "admission_date"
        ]

        if any(not form_data[field] for field in required_fields):
            flash("Please fill in all required fields.", "error")
        else:
            db = get_db()
            db.execute("""
                INSERT INTO admissions (
                    student_name, guardian_name, dob, gender, class_name,
                    phone, email, address, previous_school, admission_date, submitted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                form_data["student_name"],
                form_data["guardian_name"],
                form_data["dob"],
                form_data["gender"],
                form_data["class_name"],
                form_data["phone"],
                form_data["email"],
                form_data["address"],
                form_data["previous_school"],
                form_data["admission_date"]
            ))
            db.commit()
            db.close()
            submitted = True

    return render_template_string(
        ADMISSIONS_PAGE,
        style=BASE_STYLE,
        nav=NAV_HTML,
        form_data=form_data,
        submitted=submitted,
        student_name=form_data.get("student_name", ""),
        today=date.today().isoformat()
    )


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
        nav=NAV_HTML,
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
        nav=NAV_HTML,
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
        nav=NAV_HTML,
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
        nav=NAV_HTML,
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
        nav=NAV_HTML,
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

init_database()

if __name__ == "__main__":
    app.run(
        debug=False,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
