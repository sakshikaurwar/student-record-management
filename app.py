"""Student Record Management System - Flask application."""
import logging
import os
import re
import secrets

import mysql.connector
from mysql.connector import errorcode
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

from db import get_connection  # also loads the .env file

app = Flask(__name__)

_secret = os.getenv("SECRET_KEY")
if not _secret:
    logging.warning("SECRET_KEY is not set in .env - using an insecure development key.")
    _secret = "dev-only-key-do-not-use-in-production"
app.config["SECRET_KEY"] = _secret
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

DEPARTMENTS = [
    "Information Technology",
    "Computer Engineering",
    "Computer Science",
    "Artificial Intelligence and Data Science",
    "Electronics and Telecommunication",
    "Electrical Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
]
YEARS = [1, 2, 3, 4]

ROLL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_-]{1,29}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,99}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{10,15}$")


# ---------------------------------------------------------------- errors
class DatabaseError(Exception):
    """Raised when the database cannot be reached or a query fails."""


class DuplicateRollNumber(Exception):
    """Raised when a roll number already exists."""


# ---------------------------------------------------------------- database helper
def execute(sql, params=(), fetch=None, commit=False):
    """Run ONE parameterized query and return the result.

    fetch="all" -> list of dicts, fetch="one" -> one dict or None,
    otherwise the number of affected rows.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)  # values are passed separately -> no SQL injection
        if fetch == "all":
            result = cursor.fetchall()
        elif fetch == "one":
            result = cursor.fetchone()
        else:
            result = cursor.rowcount
        if commit:
            conn.commit()
        cursor.close()
        return result
    except mysql.connector.IntegrityError as err:
        if err.errno == errorcode.ER_DUP_ENTRY:
            raise DuplicateRollNumber() from err
        app.logger.error("Database integrity error: %s", err)
        raise DatabaseError(str(err)) from err
    except mysql.connector.Error as err:
        app.logger.error("Database error: %s", err)
        raise DatabaseError(str(err)) from err
    finally:
        if conn is not None and conn.is_connected():
            conn.close()


# ---------------------------------------------------------------- CSRF protection
def get_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


app.jinja_env.globals["csrf_token"] = get_csrf_token


@app.before_request
def protect_from_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        expected = session.get("csrf_token", "")
        if not sent or not expected or not secrets.compare_digest(sent, expected):
            abort(400, description="Your form session expired. Go back, reload the page and try again.")


# ---------------------------------------------------------------- validation
def validate_student(form):
    """Return (cleaned_values, list_of_error_messages)."""
    data = {
        "roll_number": form.get("roll_number", "").strip(),
        "full_name": " ".join(form.get("full_name", "").split()),
        "email": form.get("email", "").strip().lower(),
        "department": form.get("department", "").strip(),
        "year_of_study": form.get("year_of_study", "").strip(),
        "phone": re.sub(r"[\s-]", "", form.get("phone", "")),
    }
    errors = []

    if not data["roll_number"]:
        errors.append("Roll number is required.")
    elif not ROLL_RE.match(data["roll_number"]):
        errors.append("Roll number must be 2-30 characters: letters, numbers, - _ / only.")

    if not data["full_name"]:
        errors.append("Full name is required.")
    elif not NAME_RE.match(data["full_name"]):
        errors.append("Full name may contain only letters, spaces, . ' and - (2-100 characters).")

    if not data["email"]:
        errors.append("Email address is required.")
    elif len(data["email"]) > 150 or not EMAIL_RE.match(data["email"]):
        errors.append("Enter a valid email address.")

    if not data["department"]:
        errors.append("Department is required.")
    elif data["department"] not in DEPARTMENTS:
        errors.append("Choose a department from the list.")

    if not data["year_of_study"]:
        errors.append("Year of study is required.")
    elif not data["year_of_study"].isdigit() or int(data["year_of_study"]) not in YEARS:
        errors.append("Year of study must be between 1 and 4.")

    if not data["phone"]:
        errors.append("Phone number is required.")
    elif not PHONE_RE.match(data["phone"]):
        errors.append("Phone number must have 10-15 digits (a leading + is allowed).")

    return data, errors


# ---------------------------------------------------------------- routes
@app.route("/")
def index():
    total = execute("SELECT COUNT(*) AS total FROM students", fetch="one")["total"]
    by_department = execute(
        "SELECT department, COUNT(*) AS count FROM students "
        "GROUP BY department ORDER BY count DESC, department",
        fetch="all",
    )
    recent = execute(
        "SELECT id, roll_number, full_name, department, year_of_study, created_at "
        "FROM students ORDER BY created_at DESC, id DESC LIMIT 5",
        fetch="all",
    )
    return render_template("index.html", total=total, by_department=by_department, recent=recent)


@app.route("/students")
def students():
    q = request.args.get("q", "").strip()[:100]
    if q:
        # Escape LIKE wildcards typed by the user, then add our own for "contains" matching.
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        rows = execute(
            "SELECT * FROM students WHERE full_name LIKE %s OR roll_number LIKE %s "
            "OR department LIKE %s ORDER BY roll_number",
            (like, like, like),
            fetch="all",
        )
    else:
        rows = execute("SELECT * FROM students ORDER BY roll_number", fetch="all")
    return render_template("students.html", students=rows, q=q)


@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    form = {}
    if request.method == "POST":
        form, errors = validate_student(request.form)
        if not errors:
            try:
                execute(
                    "INSERT INTO students (roll_number, full_name, email, department, "
                    "year_of_study, phone) VALUES (%s, %s, %s, %s, %s, %s)",
                    (form["roll_number"], form["full_name"], form["email"],
                     form["department"], int(form["year_of_study"]), form["phone"]),
                    commit=True,
                )
                flash(f"Student {form['full_name']} was added.", "success")
                return redirect(url_for("students"))
            except DuplicateRollNumber:
                errors.append(f"Roll number {form['roll_number']} already exists.")
        for message in errors:
            flash(message, "danger")
    return render_template("add_student.html", form=form, departments=DEPARTMENTS, years=YEARS)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    student = execute("SELECT * FROM students WHERE id = %s", (student_id,), fetch="one")
    if student is None:
        abort(404, description="That student record does not exist.")
    form = student
    if request.method == "POST":
        form, errors = validate_student(request.form)
        if not errors:
            try:
                execute(
                    "UPDATE students SET roll_number=%s, full_name=%s, email=%s, "
                    "department=%s, year_of_study=%s, phone=%s WHERE id=%s",
                    (form["roll_number"], form["full_name"], form["email"],
                     form["department"], int(form["year_of_study"]), form["phone"], student_id),
                    commit=True,
                )
                flash(f"Student {form['full_name']} was updated.", "success")
                return redirect(url_for("students"))
            except DuplicateRollNumber:
                errors.append(f"Roll number {form['roll_number']} already belongs to another student.")
        for message in errors:
            flash(message, "danger")
    return render_template("edit_student.html", form=form, student_id=student_id,
                           departments=DEPARTMENTS, years=YEARS)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    deleted = execute("DELETE FROM students WHERE id = %s", (student_id,), commit=True)
    if deleted:
        flash("Student record deleted.", "success")
    else:
        flash("That student record was already removed.", "danger")
    return redirect(url_for("students"))


@app.route("/health")
def health():
    """Simple check used for troubleshooting: confirms the app can reach the database."""
    execute("SELECT 1", fetch="one")
    return {"status": "ok", "database": "connected"}


# ---------------------------------------------------------------- error pages
@app.errorhandler(DatabaseError)
def handle_database_error(err):
    return render_template(
        "error.html",
        code=503,
        title="Database unavailable",
        message="The application could not complete the database request. "
                "Check that MySQL is running and that the DB_* values in .env are correct.",
    ), 503


@app.errorhandler(HTTPException)
def handle_http_error(err):
    return render_template("error.html", code=err.code, title=err.name,
                           message=err.description), err.code


if __name__ == "__main__":
    # Development server only. In production Gunicorn imports "app:app".
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
