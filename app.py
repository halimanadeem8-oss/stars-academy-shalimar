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
            applicant_name TEXT NOT NULL,
            guardian_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            class_applied TEXT NOT NULL,
            previous_school TEXT DEFAULT '',
            message TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'New',
            created_at TEXT NOT NULL
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
:root{
    --navy:#0b1736;
    --navy-2:#142653;
    --gold:#d8b45a;
    --gold-light:#f4e7bd;
    --ink:#172033;
    --muted:#6b7485;
    --bg:#f4f7fb;
    --white:#ffffff;
    --green:#2e9d62;
    --red:#d9534f;
    --border:#e4e8ef;
    --shadow:0 12px 35px rgba(11,23,54,.08);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{
    margin:0;
    font-family:Inter,Segoe UI,Arial,Helvetica,sans-serif;
    background:var(--bg);
    color:var(--ink);
}
a{text-decoration:none;color:inherit}
button,input,select,textarea{font-family:inherit}
button{cursor:pointer}

/* TOP NAVIGATION */
.navbar{
    height:74px;
    background:rgba(11,23,54,.98);
    color:white;
    display:flex;
    align-items:center;
    gap:18px;
    padding:0 24px;
    position:sticky;
    top:0;
    z-index:1000;
    box-shadow:0 4px 20px rgba(0,0,0,.12);
}
.menu-toggle{
    width:44px;height:44px;border:1px solid rgba(255,255,255,.15);
    background:rgba(255,255,255,.07);color:#fff;border-radius:10px;
    font-size:23px;display:flex;align-items:center;justify-content:center;
}
.menu-toggle:hover{background:rgba(255,255,255,.14)}
.brand{font-size:21px;font-weight:800;line-height:1.05;white-space:nowrap}
.brand small{display:block;font-size:11px;color:var(--gold);margin-top:5px;letter-spacing:.4px}
.top-links{margin-left:auto;display:flex;align-items:center;gap:7px}
.top-link{padding:10px 13px;border-radius:8px;color:#eef2ff;font-size:14px;font-weight:600}
.top-link:hover,.top-link.active{background:rgba(216,180,90,.16);color:#fff}
.user-chip{font-size:13px;color:#dce3f5;margin-left:8px}
.logout-btn{background:#d9534f;color:white;padding:10px 15px;border-radius:8px;font-weight:700}
.logout-btn:hover{background:#c73f3b}

/* SLIDE MENU */
.overlay{
    position:fixed;inset:0;background:rgba(4,10,25,.45);
    z-index:1100;opacity:0;visibility:hidden;transition:.25s ease;
}
.overlay.open{opacity:1;visibility:visible}
.side-menu{
    position:fixed;top:0;left:0;height:100vh;width:310px;max-width:86vw;
    background:#fff;z-index:1200;transform:translateX(-105%);
    transition:transform .28s ease;box-shadow:12px 0 35px rgba(0,0,0,.16);
    display:flex;flex-direction:column;
}
.side-menu.open{transform:translateX(0)}
.side-head{
    background:linear-gradient(135deg,var(--navy),var(--navy-2));
    color:#fff;padding:25px 22px 21px;
}
.side-head strong{font-size:20px}
.side-head span{display:block;color:var(--gold);font-size:12px;margin-top:5px}
.side-close{
    float:right;background:transparent;border:0;color:#fff;font-size:26px;
    line-height:1;padding:0;
}
.side-links{padding:16px 12px;overflow:auto}
.side-link{
    display:flex;align-items:center;gap:13px;padding:13px 14px;margin:4px 0;
    border-radius:10px;color:#26324a;font-weight:600;
}
.side-link:hover{background:#f1f4f9;color:var(--navy)}
.side-link.logout{color:#c33b37;margin-top:8px;border-top:1px solid var(--border);border-radius:0;padding-top:20px}
.side-icon{width:24px;text-align:center;font-size:18px}

/* CONTENT */
.container{max-width:1280px;margin:auto;padding:32px 28px}
.page-title{margin:0 0 6px;font-size:31px}
.subtitle{color:var(--muted);margin:0 0 25px}
.hero{
    position:relative;overflow:hidden;border-radius:22px;padding:48px;
    background:linear-gradient(135deg,#0b1736 0%,#1b3470 100%);color:#fff;
    box-shadow:var(--shadow);margin-bottom:28px;
}
.hero:after{
    content:"";position:absolute;width:330px;height:330px;border-radius:50%;
    right:-110px;top:-130px;background:rgba(216,180,90,.12);
}
.hero-content{position:relative;z-index:1;max-width:760px}
.hero-kicker{color:var(--gold);font-weight:800;letter-spacing:1.5px;text-transform:uppercase;font-size:12px}
.hero h1{font-size:46px;line-height:1.08;margin:13px 0}
.hero p{font-size:17px;line-height:1.75;color:#dce5fb;max-width:680px}
.hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:25px}
.hero-btn{display:inline-flex;align-items:center;justify-content:center;padding:12px 18px;border-radius:9px;font-weight:800}
.hero-btn.primary{background:var(--gold);color:var(--navy)}
.hero-btn.secondary{border:1px solid rgba(255,255,255,.28);color:#fff;background:rgba(255,255,255,.07)}
.hero-btn:hover{transform:translateY(-1px)}
.section{margin:42px 0;scroll-margin-top:95px}
.section-heading{display:flex;align-items:end;justify-content:space-between;gap:20px;margin-bottom:18px}
.section-heading h2{margin:0;font-size:28px}
.section-heading p{margin:4px 0 0;color:var(--muted)}
.cards-3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.info-card,.panel,.stat-card,.form-card,.student-table-wrapper,.contact-card{
    background:#fff;border:1px solid rgba(228,232,239,.8);border-radius:16px;
    box-shadow:var(--shadow);
}
.info-card{padding:23px}
.info-card .icon{font-size:27px;margin-bottom:10px}
.info-card h3{margin:0 0 8px}
.info-card p{color:var(--muted);line-height:1.65;margin:0}
.program-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}
.program{padding:20px;background:#fff;border-radius:14px;border:1px solid var(--border);box-shadow:0 7px 24px rgba(11,23,54,.05)}
.program strong{display:block;color:var(--navy);margin-bottom:7px}
.program span{font-size:13px;color:var(--muted);line-height:1.5}
.principal{
    display:grid;grid-template-columns:280px 1fr;gap:30px;align-items:center;
    background:linear-gradient(135deg,#fff,#f9f5e8);border:1px solid #eee2bd;
    border-radius:20px;padding:28px;box-shadow:var(--shadow)
}
.principal-photo{
    width:240px;height:270px;border-radius:18px;object-fit:cover;
    display:block;margin:auto;background:#e9edf5;border:5px solid #fff;
    box-shadow:0 12px 30px rgba(11,23,54,.13)
}
.principal h2{margin:0 0 7px}
.principal .role{color:#9a7927;font-weight:800;margin-bottom:15px}
.principal blockquote{margin:0;color:#49546a;line-height:1.8;font-size:16px}
.contact-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.contact-card{padding:22px}
.contact-card strong{display:block;margin-bottom:7px;color:var(--navy)}
.contact-card span{color:var(--muted);line-height:1.6}

/* STATS / DASHBOARD */
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:25px}
.stat-card{padding:24px;border-left:5px solid var(--gold)}
.present-card{border-left-color:var(--green)}
.absent-card{border-left-color:var(--red)}
.total-card{border-left-color:var(--gold)}
.stat-title{color:var(--muted);font-size:13px;font-weight:700;margin-bottom:9px}
.stat-number{font-size:36px;font-weight:800}
.dashboard-grid{display:grid;grid-template-columns:1.5fr 1fr;gap:25px}
.panel{padding:25px}
.panel h2{margin-top:0}
.graph{display:flex;align-items:flex-end;justify-content:center;gap:70px;height:280px;padding:20px;border-bottom:2px solid #e8ebf0}
.bar-wrapper{height:230px;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;width:100px}
.bar{width:70px;min-height:8px;border-radius:8px 8px 0 0}
.present-bar{background:var(--green)}
.absent-bar{background:var(--red)}
.bar-number{font-weight:800;margin-bottom:8px}.bar-label{margin-top:10px;font-weight:700}
.attendance-percent{font-size:42px;font-weight:800;color:var(--navy);margin:20px 0 5px}
.date-text{color:var(--muted)}
.menu-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:20px}
.menu-button{background:var(--navy);color:#fff;padding:14px;border-radius:9px;text-align:center;font-weight:700}
.menu-button:hover{background:#1b3470}

/* TABLES / FORMS */
.toolbar{background:#fff;padding:18px;border-radius:14px;box-shadow:var(--shadow);display:flex;gap:12px;align-items:center;margin-bottom:20px}
.search-box,.select-box,.form-group input,.form-group select,.form-group textarea{
    padding:13px;border:1px solid #d7dce5;border-radius:8px;outline:none;font-size:14px
}
.search-box{flex:1}.search-box:focus,.select-box:focus,.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:var(--gold)}
.gold-button{display:inline-block;background:var(--gold);color:var(--navy);padding:13px 18px;border:none;border-radius:8px;font-weight:800;cursor:pointer}
.gold-button:hover{background:#c8a54d}
.blue-button{display:inline-block;background:var(--navy);color:#fff;padding:9px 13px;border-radius:6px;border:none;cursor:pointer}
.red-button{background:var(--red);color:#fff;padding:9px 13px;border-radius:6px;border:none;cursor:pointer}
.green-button{background:var(--green);color:#fff;padding:9px 13px;border-radius:6px;border:none;cursor:pointer}
.student-table-wrapper{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{background:var(--navy);color:#fff;padding:15px;text-align:left}
td{padding:14px 15px;border-bottom:1px solid #edf0f5}
tr:hover{background:#fafbfc}
.status{display:inline-block;padding:6px 10px;border-radius:20px;font-size:12px;font-weight:800}
.paid,.present-status{background:#dff5e8;color:#227a4b}
.unpaid,.absent-status{background:#fde3e2;color:#b43a36}
.partial{background:#fff2cc;color:#876d00}.not-marked-status{background:#eef1f5;color:#697386}
.action-buttons{display:flex;gap:7px;flex-wrap:wrap}
.form-card{max-width:720px;margin:auto;padding:30px}
.form-group{margin-bottom:18px}.form-group label{display:block;margin-bottom:7px;font-weight:700}
.form-group input,.form-group select,.form-group textarea{width:100%}
.form-group textarea{min-height:110px;resize:vertical}
.form-submit{width:100%;padding:14px;background:var(--navy);color:#fff;border:none;border-radius:8px;font-weight:800;cursor:pointer}
.form-submit:hover{background:#182957}
.alert{padding:13px 17px;border-radius:8px;margin-bottom:18px;background:#fff2cc;color:#705c00}
.success{background:#dff5e8;color:#227a4b}.error{background:#fde3e2;color:#a82f2b}
.back-button{display:inline-block;margin-bottom:20px;color:var(--navy);font-weight:800}
.admission-status{font-size:12px;font-weight:800;color:#9a7927;background:#fff4cf;padding:5px 9px;border-radius:15px}

/* LOGIN - kept visually separate; Google logic unchanged */
.login-page{min-height:100vh;display:flex;justify-content:center;align-items:center;background:linear-gradient(135deg,var(--navy),#1d2d5a);padding:20px}
.login-box{width:100%;max-width:420px;background:#fff;padding:40px;border-radius:18px;box-shadow:0 15px 45px rgba(0,0,0,.25)}
.login-title{text-align:center;color:var(--navy);font-size:30px;margin-bottom:5px}
.login-subtitle{text-align:center;color:var(--muted);margin-bottom:30px}
.login-button{width:100%;padding:14px;border:none;border-radius:8px;background:var(--gold);color:var(--navy);font-weight:800;cursor:pointer;font-size:16px}
.login-button:hover{background:#c8a54d}

/* FOOTER */
.site-footer{margin-top:55px;background:var(--navy);color:#dce3f5;padding:28px;text-align:center}
.site-footer strong{color:#fff}.site-footer small{display:block;margin-top:7px;color:#aeb9d2}

/* RESPONSIVE */
@media(max-width:1050px){
    .top-links{display:none}.cards-3,.contact-grid{grid-template-columns:1fr}
    .program-grid{grid-template-columns:repeat(2,1fr)}
    .principal{grid-template-columns:1fr;text-align:center}
}
@media(max-width:850px){
    .stats{grid-template-columns:1fr}.dashboard-grid{grid-template-columns:1fr}
    .toolbar{flex-direction:column;align-items:stretch}.menu-grid{grid-template-columns:1fr}
    .navbar{padding:0 14px}.brand{font-size:18px}.container{padding:22px 15px}
    .graph{gap:35px}.hero{padding:32px 24px}.hero h1{font-size:35px}
    .program-grid{grid-template-columns:1fr}.principal-photo{width:210px;height:235px}
}
@media(max-width:520px){
    .user-chip{display:none}.hero{padding:28px 20px}.hero h1{font-size:30px}
    .hero p{font-size:15px}.menu-grid{grid-template-columns:1fr}
}
</style>
"""


NAV_HTML = """
<div class="overlay" id="menuOverlay" onclick="closeAcademyMenu()"></div>

<aside class="side-menu" id="academySideMenu">
    <div class="side-head">
        <button class="side-close" onclick="closeAcademyMenu()" aria-label="Close menu">&times;</button>
        <strong>Stars Academy</strong>
        <span>Shalimar Branch</span>
    </div>
    <nav class="side-links">
        <a class="side-link" href="{{ url_for('dashboard') }}" onclick="closeAcademyMenu()"><span class="side-icon">⌂</span> Home</a>
        <a class="side-link" href="{{ url_for('students') }}" onclick="closeAcademyMenu()"><span class="side-icon">👨‍🎓</span> Students</a>
        <a class="side-link" href="{{ url_for('attendance') }}" onclick="closeAcademyMenu()"><span class="side-icon">✓</span> Attendance</a>
        <a class="side-link" href="{{ url_for('admissions') }}" onclick="closeAcademyMenu()"><span class="side-icon">📝</span> Admissions</a>
        <a class="side-link" href="{{ url_for('dashboard') }}#faculty" onclick="closeAcademyMenu()"><span class="side-icon">👩‍🏫</span> Faculty</a>
        <a class="side-link" href="{{ url_for('dashboard') }}#announcements" onclick="closeAcademyMenu()"><span class="side-icon">📢</span> Announcements</a>
        <a class="side-link" href="{{ url_for('dashboard') }}#about" onclick="closeAcademyMenu()"><span class="side-icon">ℹ</span> About Academy</a>
        <a class="side-link" href="{{ url_for('dashboard') }}#contact" onclick="closeAcademyMenu()"><span class="side-icon">☎</span> Contact</a>
        <a class="side-link logout" href="{{ url_for('logout') }}"><span class="side-icon">↪</span> Logout</a>
    </nav>
</aside>

<header class="navbar">
    <button class="menu-toggle" onclick="openAcademyMenu()" aria-label="Open menu">☰</button>
    <a href="{{ url_for('dashboard') }}" class="brand">Stars Academy<small>Shalimar Branch</small></a>
    <nav class="top-links">
        <a class="top-link" href="{{ url_for('dashboard') }}">Home</a>
        <a class="top-link" href="{{ url_for('dashboard') }}#about">About</a>
        <a class="top-link" href="{{ url_for('dashboard') }}#contact">Contact</a>
        <a class="top-link" href="{{ url_for('admissions') }}">Admissions</a>
    </nav>
    <span class="user-chip">Academy Management</span>
</header>

<script>
function openAcademyMenu(){
    document.getElementById("academySideMenu").classList.add("open");
    document.getElementById("menuOverlay").classList.add("open");
    document.body.style.overflow="hidden";
}
function closeAcademyMenu(){
    document.getElementById("academySideMenu").classList.remove("open");
    document.getElementById("menuOverlay").classList.remove("open");
    document.body.style.overflow="";
}
document.addEventListener("keydown", function(e){
    if(e.key === "Escape") closeAcademyMenu();
});
</script>
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
    <title>Home | Stars Academy</title>
    {{ style|safe }}
</head>
<body>
{{ nav_html|safe }}

<main class="container">

    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="alert {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endwith %}

    <section class="hero" id="home">
        <div class="hero-content">
            <div class="hero-kicker">Shalimar Branch • Academy Management</div>
            <h1>Welcome to Stars Academy</h1>
            <p>
                A focused learning environment where students are guided to build
                strong academic foundations, confidence, discipline and a brighter future.
            </p>
            <div class="hero-actions">
                <a class="hero-btn primary" href="{{ url_for('admissions') }}">Apply for Admission</a>
                <a class="hero-btn secondary" href="#about">Explore Academy</a>
            </div>
        </div>
    </section>

    <section class="stats">
        <div class="stat-card total-card">
            <div class="stat-title">TOTAL STUDENTS</div>
            <div class="stat-number">{{ total_students }}</div>
        </div>
        <div class="stat-card present-card">
            <div class="stat-title">PRESENT TODAY</div>
            <div class="stat-number">{{ present }}</div>
        </div>
        <div class="stat-card absent-card">
            <div class="stat-title">ABSENT TODAY</div>
            <div class="stat-number">{{ absent }}</div>
        </div>
    </section>

    <section class="section" id="about">
        <div class="section-heading">
            <div>
                <h2>About Stars Academy</h2>
                <p>Learning with purpose, discipline and care.</p>
            </div>
        </div>
        <div class="cards-3">
            <article class="info-card">
                <div class="icon">🎓</div>
                <h3>Academic Excellence</h3>
                <p>Structured learning and focused academic support designed to help students progress with confidence.</p>
            </article>
            <article class="info-card">
                <div class="icon">🌟</div>
                <h3>Student Development</h3>
                <p>We value discipline, confidence, communication and the personal growth of every learner.</p>
            </article>
            <article class="info-card">
                <div class="icon">🤝</div>
                <h3>Supportive Environment</h3>
                <p>A respectful academy environment where students can ask questions, learn and improve every day.</p>
            </article>
        </div>
    </section>

    <section class="section" id="programs">
        <div class="section-heading">
            <div>
                <h2>Academic Programs</h2>
                <p>Current student categories managed by the academy.</p>
            </div>
        </div>
        <div class="program-grid">
            <div class="program"><strong>Class 9</strong><span>Foundation and board-focused academic preparation.</span></div>
            <div class="program"><strong>Class 10</strong><span>Focused preparation, revision and examination support.</span></div>
            <div class="program"><strong>1st Year</strong><span>Higher-secondary studies with structured academic guidance.</span></div>
            <div class="program"><strong>2nd Year</strong><span>Advanced preparation and final-stage examination support.</span></div>
        </div>
    </section>

    <section class="section" id="faculty">
        <div class="section-heading">
            <div>
                <h2>Our Learning Community</h2>
                <p>People and systems working together for students.</p>
            </div>
        </div>
        <div class="cards-3">
            <article class="info-card"><div class="icon">👩‍🏫</div><h3>Dedicated Faculty</h3><p>Teachers focused on clear explanations, practice and student progress.</p></article>
            <article class="info-card"><div class="icon">📚</div><h3>Organised Learning</h3><p>Student records and attendance are kept organised through the academy dashboard.</p></article>
            <article class="info-card"><div class="icon">🏆</div><h3>Future Focused</h3><p>We encourage students to set goals, stay consistent and work towards their ambitions.</p></article>
        </div>
    </section>

    <section class="section" id="announcements">
        <div class="section-heading">
            <div>
                <h2>Announcements</h2>
                <p>Important academy updates.</p>
            </div>
        </div>
        <div class="panel">
            <p style="margin:0;color:#59657a;line-height:1.7;">
                Welcome to the Stars Academy management portal. Please check with the
                academy administration for the latest class schedules, examination dates,
                admission updates and notices.
            </p>
        </div>
    </section>

    <section class="section">
        <div class="principal">
            <div>
                <img class="principal-photo"
                     src="{{ principal_photo_url }}"
                     alt="Principal Halima">
            </div>
            <div>
                <h2>Message from the Principal</h2>
                <div class="role">Principal Halima • Stars Academy, Shalimar Branch</div>
                <blockquote>
                    “At Stars Academy, we believe that every student has the ability to
                    learn, grow and achieve meaningful goals. Our aim is to provide a
                    disciplined, supportive and inspiring environment where students can
                    develop strong academic foundations while becoming confident and
                    responsible individuals. We look forward to working together with
                    our students and families for a successful future.”
                </blockquote>
            </div>
        </div>
    </section>

    <section class="section" id="contact">
        <div class="section-heading">
            <div>
                <h2>Contact & Information</h2>
                <p>Stars Academy • Shalimar Branch</p>
            </div>
        </div>
        <div class="contact-grid">
            <div class="contact-card"><strong>📍 Branch</strong><span>Shalimar Branch, Lahore</span></div>
            <div class="contact-card"><strong>📞 Phone</strong><span>Contact the academy administration for admissions and enquiries.</span></div>
            <div class="contact-card"><strong>✉️ Admissions</strong><span>Use the Admissions section to submit an enquiry or application.</span></div>
        </div>
    </section>

    <section class="section" style="margin-bottom:10px">
        <div class="panel" style="display:flex;justify-content:space-between;align-items:center;gap:18px;flex-wrap:wrap">
            <div>
                <h2 style="margin:0 0 6px">Manage the Academy</h2>
                <p style="margin:0;color:var(--muted)">Access student records and daily attendance from the menu.</p>
            </div>
            <div class="hero-actions" style="margin-top:0">
                <a class="gold-button" href="{{ url_for('students') }}">Manage Students</a>
                <a class="blue-button" href="{{ url_for('attendance') }}">Manage Attendance</a>
            </div>
        </div>
    </section>
</main>

<footer class="site-footer">
    <strong>Stars Academy | Shalimar Branch</strong>
    <small>Principal Halima • Academy Management Portal</small>
</footer>
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
{{ nav_html|safe }}

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
{{ nav_html|safe }}

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
{{ nav_html|safe }}

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
# ADMISSIONS PAGE
# ============================================================

ADMISSIONS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Admissions | Stars Academy</title>
    {{ style|safe }}
</head>
<body>
{{ nav_html|safe }}

<main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% for category, message in messages %}
            <div class="alert {{ category }}">{{ message }}</div>
        {% endfor %}
    {% endwith %}

    <div class="section-heading">
        <div>
            <h1 class="page-title">Admissions</h1>
            <p class="subtitle">Submit and manage admission enquiries for Stars Academy.</p>
        </div>
    </div>

    <div class="dashboard-grid">
        <section class="form-card" style="max-width:none">
            <h2 style="margin-top:0">New Admission Application</h2>
            <p class="subtitle">Enter the applicant's information below.</p>

            <form method="POST">
                <div class="form-group">
                    <label>Applicant / Student Name</label>
                    <input type="text" name="applicant_name" placeholder="Enter full name" required>
                </div>
                <div class="form-group">
                    <label>Parent / Guardian Name</label>
                    <input type="text" name="guardian_name" placeholder="Enter parent or guardian name" required>
                </div>
                <div class="form-group">
                    <label>Phone Number</label>
                    <input type="text" name="phone" placeholder="03XXXXXXXXX" required>
                </div>
                <div class="form-group">
                    <label>Class Applying For</label>
                    <select name="class_applied" required>
                        <option value="">Select Class</option>
                        <option value="9">9</option>
                        <option value="10">10</option>
                        <option value="1st Year">1st Year</option>
                        <option value="2nd Year">2nd Year</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Previous School <span style="font-weight:400;color:#7b8494">(optional)</span></label>
                    <input type="text" name="previous_school" placeholder="Previous school name">
                </div>
                <div class="form-group">
                    <label>Message / Notes <span style="font-weight:400;color:#7b8494">(optional)</span></label>
                    <textarea name="message" placeholder="Any admission questions or notes..."></textarea>
                </div>
                <button class="form-submit" type="submit">SUBMIT ADMISSION</button>
            </form>
        </section>

        <section>
            <div class="panel">
                <h2 style="margin-top:0">Admission Process</h2>
                <p style="color:var(--muted);line-height:1.7">1. Submit the applicant's details.</p>
                <p style="color:var(--muted);line-height:1.7">2. Academy administration reviews the application.</p>
                <p style="color:var(--muted);line-height:1.7">3. Contact the parent/guardian for further information.</p>
                <p style="color:var(--muted);line-height:1.7">4. Complete enrolment and add the student to the student records.</p>
            </div>
        </section>
    </div>

    <section class="section">
        <div class="section-heading">
            <div>
                <h2>Admission Applications</h2>
                <p>Recent applications submitted through this portal.</p>
            </div>
        </div>
        <div class="student-table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Applicant</th>
                        <th>Guardian</th>
                        <th>Phone</th>
                        <th>Class</th>
                        <th>Previous School</th>
                        <th>Status</th>
                        <th>Date</th>
                    </tr>
                </thead>
                <tbody>
                    {% if applications %}
                        {% for item in applications %}
                        <tr>
                            <td><strong>{{ item['applicant_name'] }}</strong></td>
                            <td>{{ item['guardian_name'] }}</td>
                            <td>{{ item['phone'] }}</td>
                            <td>{{ item['class_applied'] }}</td>
                            <td>{{ item['previous_school'] or '—' }}</td>
                            <td><span class="admission-status">{{ item['status'] }}</span></td>
                            <td>{{ item['created_at'] }}</td>
                        </tr>
                        {% endfor %}
                    {% else %}
                        <tr><td colspan="7" style="text-align:center;padding:30px">No admission applications yet.</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>
    </section>
</main>

<footer class="site-footer">
    <strong>Stars Academy | Shalimar Branch</strong>
    <small>Admissions Office • Principal Halima</small>
</footer>
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
        nav_html=NAV_HTML,
        principal_photo_url=os.environ.get("PRINCIPAL_PHOTO_URL", "data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"600\" height=\"700\" viewBox=\"0 0 600 700\"><rect width=\"600\" height=\"700\" fill=\"%23eef1f7\"/><circle cx=\"300\" cy=\"250\" r=\"105\" fill=\"%23d7b28c\"/><path d=\"M190 245c12-110 210-130 220 0-38-55-66-66-110-64-45-2-77 20-110 64z\" fill=\"%232b1d2b\"/><path d=\"M165 660c12-170 73-220 135-220s123 50 135 220\" fill=\"%230b1736\"/><text x=\"300\" y=\"610\" text-anchor=\"middle\" font-family=\"Arial\" font-size=\"42\" font-weight=\"bold\" fill=\"%23d8b45a\">PRINCIPAL</text></svg>"),
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
        nav_html=NAV_HTML,
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
        nav_html=NAV_HTML,
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
        nav_html=NAV_HTML,
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
        nav_html=NAV_HTML,
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
# ADMISSIONS
# ============================================================

@app.route("/admissions", methods=["GET", "POST"])
@login_required
def admissions():

    if request.method == "POST":
        applicant_name = request.form.get("applicant_name", "").strip()
        guardian_name = request.form.get("guardian_name", "").strip()
        phone = request.form.get("phone", "").strip()
        class_applied = request.form.get("class_applied", "").strip()
        previous_school = request.form.get("previous_school", "").strip()
        message = request.form.get("message", "").strip()

        if not applicant_name or not guardian_name or not phone or not class_applied:
            flash("Please complete all required admission fields.", "error")
            return redirect(url_for("admissions"))

        db = get_db()
        db.execute("""
            INSERT INTO admissions
            (applicant_name, guardian_name, phone, class_applied, previous_school, message, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'New', ?)
        """, (
            applicant_name,
            guardian_name,
            phone,
            class_applied,
            previous_school,
            message,
            date.today().isoformat()
        ))
        db.commit()
        db.close()

        flash("Admission application submitted successfully.", "success")
        return redirect(url_for("admissions"))

    db = get_db()
    applications = db.execute("""
        SELECT * FROM admissions
        ORDER BY id DESC
    """).fetchall()
    db.close()

    return render_template_string(
        ADMISSIONS_PAGE,
        style=BASE_STYLE,
        nav_html=NAV_HTML,
        applications=applications
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
