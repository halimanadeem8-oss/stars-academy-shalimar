from flask import Flask, request, redirect, url_for, session, render_template_string, flash, send_from_directory
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

app = Flask(__name__)

# Serve the principal picture uploaded in the repository root.
@app.route("/principal.jfif")
def principal_picture():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "principal.jfif")

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
.form-card{max-width:650px;background:#fff;border:1px solid #e8edf5;border-radius:16px;padding:28px;box-shadow:0 5px 22px rgba(20,34,65,.07)}.form-group{margin-bottom:17px}.form-group label{display:block;font-weight:800;margin-bottom:7px}.form-group input,.form-group select{width:100%}.form-submit{width:100%;margin-top:8px}.admission-card{max-width:900px}.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.form-group.full{grid-column:1 / -1}.required-star{color:#b43a36}.success-box{background:#dff4e9;color:#176344;border:1px solid #b9e3cc;padding:16px;border-radius:12px;margin-bottom:20px;font-weight:700}.success-box span{display:block;font-weight:500;margin-top:5px}.form-help{font-size:12px;color:#7a8494;margin-top:5px}.back-button{display:inline-block;margin-bottom:18px;color:#6d5721;font-weight:800}
.alert{padding:11px 14px;border-radius:9px;margin:12px 0}.alert.error{background:#fde4e4;color:#9c2e2e}.alert.success{background:#dff4e9;color:#176344}
.login-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:25px;background:linear-gradient(135deg,#101b3d,#1c315f)}.login-box{width:min(430px,100%);background:#fff;border-radius:20px;padding:34px;box-shadow:0 18px 55px rgba(0,0,0,.22)}.login-title{text-align:center;color:#101b3d;margin:0}.login-subtitle{text-align:center;color:#687386;line-height:1.6;margin:7px 0 25px}.login-box .form-group input{width:100%}.login-button{width:100%;border:0;border-radius:9px;background:#c9a54a;color:#101b3d;padding:12px;font-weight:900;cursor:pointer}
.footer{margin-top:35px;padding:25px;text-align:center;color:#7a8494;font-size:13px}
@media(max-width:800px){
html,body{width:100%;max-width:100%;overflow-x:hidden}
.navbar{height:64px;padding:0 12px}
.brand{font-size:18px}.brand small{font-size:9px}
.nav-right>span,.nav-link{display:none}
.container{width:100%;max-width:100%;padding:22px 14px 45px;margin:0}
.hero{padding:25px 20px;border-radius:15px}.hero h1{font-size:28px;line-height:1.2}.hero p{font-size:14px}
.page-title{font-size:27px}
.stats,.info-grid,.dashboard-grid{grid-template-columns:1fr}
.stat-card,.panel,.info-card{width:100%}
.menu-grid{grid-template-columns:1fr}
.principal-card{flex-direction:column;text-align:center;padding:20px}
.principal-photo{width:125px;height:125px}
.toolbar{flex-direction:column}.search-box{min-width:0;width:100%}
.toolbar select,.toolbar button,.toolbar a{width:100%;text-align:center}
.form-grid{grid-template-columns:1fr}.form-group.full{grid-column:auto}
.form-card{width:100%;max-width:100%;padding:20px}
.login-page{padding:15px}.login-box{width:100%;max-width:430px;padding:25px 20px}
.student-table-wrapper{width:100%;max-width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch}
table{min-width:700px}
.graph{gap:35px}.footer{padding:20px 10px}
}
@media(max-width:480px){
.container{padding-left:12px;padding-right:12px}
.hero h1{font-size:25px}.hero{padding:22px 17px}
.stat-number{font-size:30px}.attendance-percent{font-size:42px}
.panel,.stat-card,.info-card{padding:18px}.form-card{padding:17px}
}
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
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Stars Academy | Login</title>{{ style|safe }}</head>
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
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Home | Stars Academy</title>{{ style|safe }}</head><body>
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

<section class="section" id="principal"><h2>Principal's Message</h2><div class="principal-card"><img class="principal-photo" src="/principal.jfif" alt="Principal Halima"><div><h3 style="margin:0;color:#101b3d">Principal Halima</h3><p style="color:#687386;line-height:1.7">“Our aim is to provide students with a focused, respectful and encouraging environment where every student can grow.”</p></div></div></section>

<section class="section" id="contact"><h2>Contact</h2><div class="info-grid"><div class="info-card"><h3>Branch</h3><p>Stars Academy<br>Shalimar Branch</p></div><div class="info-card"><h3>Office</h3><p>For admissions and academy information, contact the branch office.</p></div><div class="info-card"><h3>Management</h3><p>Academy management can use this dashboard to maintain student records and attendance.</p></div></div></section>
<div class="footer">© Stars Academy | Shalimar Branch</div>
</div></body></html>
"""

STUDENTS_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Students | Stars Academy</title>{{ style|safe }}</head><body>
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
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>{{ page_title }} | Stars Academy</title>{{ style|safe }}</head><body>
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
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Attendance | Stars Academy</title>{{ style|safe }}</head><body>
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
