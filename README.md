# Student Record Management System

A small Flask + MySQL web application for managing student records (add, view, search, edit, delete, dashboard). It runs locally on Windows first, then moves to AWS (EC2 for the app, RDS for the database) by changing only the `.env` file. The AWS steps are in [`AWS_DEPLOYMENT.md`](AWS_DEPLOYMENT.md).

## Project structure

```
StudentRecordManagement/
├── app.py                  Flask routes, validation, error handling
├── db.py                   MySQL connection (reads environment variables)
├── requirements.txt        Python dependencies
├── database.sql            Creates the database, table and sample data
├── .env.example            Template for your private .env file
├── .gitignore
├── README.md
├── AWS_DEPLOYMENT.md
├── templates/
│   ├── base.html           Layout: navbar, alerts, footer
│   ├── index.html          Dashboard
│   ├── students.html       Student table + search
│   ├── add_student.html
│   ├── edit_student.html
│   ├── _student_form.html  Form shared by add and edit
│   └── error.html          Friendly error page (404, 400, database down)
└── static/css/style.css
```

## Architecture

Local development:

```
Browser ──► Flask dev server (127.0.0.1:5000) ──► MySQL 8 (localhost:3306)
```

On AWS:

```
                         ┌──────────────────── AWS VPC ────────────────────┐
                         │  EC2 instance (public subnet)                   │
Browser ──HTTP :80──►    │   Nginx ──► Gunicorn (127.0.0.1:8000) ──► Flask │
                         │                                      │          │
                         │                         MySQL :3306  │          │
                         │                   (only from EC2 SG) ▼          │
                         │  RDS MySQL 8 (not publicly accessible)          │
                         └─────────────────────────────────────────────────┘
```

## Run locally on Windows

Commands below work in **Command Prompt** unless noted. `<project folder>` means the folder that contains `app.py`.

### 1. Install Python and MySQL 8

1. Python 3.10 or newer from https://www.python.org/downloads/ . On the first installer screen tick **Add python.exe to PATH**.
2. MySQL 8 from https://dev.mysql.com/downloads/installer/ . Choose **Server only** (add MySQL Workbench if you want a GUI). Set a root password and keep the Windows service name `MySQL80`.
3. Check both (any folder):

```
python --version
```

### 2. Create and activate a virtual environment

Run in `<project folder>`:

```
cd %USERPROFILE%\Documents\StudentRecordManagement
python -m venv venv
venv\Scripts\activate
```

In PowerShell, activate with `.\venv\Scripts\Activate.ps1`. If PowerShell blocks scripts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first. The prompt starts with `(venv)` when it worked.

### 3. Install dependencies

Run in `<project folder>` with the virtual environment active:

```
pip install -r requirements.txt
```

### 4. Start the MySQL service

Open Command Prompt **as Administrator** (any folder):

```
net start MySQL80
```

If it says the service is already started, that is fine. If the name is unknown, run `sc query type= service state= all | findstr /i mysql` to find it.

### 5. Create the database and table

`mysql.exe` is usually not on PATH. Add it for this window, then start the client **from `<project folder>`**:

```
set PATH=%PATH%;C:\Program Files\MySQL\MySQL Server 8.0\bin
mysql -u root -p
```

At the `mysql>` prompt:

```sql
SOURCE database.sql;
SHOW TABLES FROM student_management;
```

You should see `students`, and `SELECT COUNT(*) FROM student_management.students;` should return 5 sample rows.

### 6. Create the dedicated application user

Still at the `mysql>` prompt (choose your own strong password; avoid spaces, quotes and `#`):

```sql
CREATE USER 'student_app'@'localhost' IDENTIFIED BY 'YourStrongPassword1';
GRANT SELECT, INSERT, UPDATE, DELETE ON student_management.* TO 'student_app'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

The app never uses `root`. This account can read and change rows in this one database only.

### 7. Create the `.env` file

In `<project folder>`:

```
copy .env.example .env
notepad .env
```

Set `DB_PASSWORD` to the password from step 6. Generate a value for `SECRET_KEY` with:

```
python -c "import secrets; print(secrets.token_hex(32))"
```

### 8. Run the application

In `<project folder>` with `(venv)` active:

```
python app.py
```

### 9. Open it

Go to http://127.0.0.1:5000 . Check http://127.0.0.1:5000/health : it should show `"database": "connected"`.

Stop the server with `Ctrl + C`.

### 10. Test it

Use the checklist below.

## GitHub commands

Run in `<project folder>`. Do this once, and replace the name and URL with yours.

```
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
git init
git status
```

`git status` must **not** list `.env` or `venv/`. If it does, `.gitignore` is missing or misnamed. Then:

```
git add .
git status
git commit -m "Initial commit: Student Record Management System"
```

Create an empty repository on https://github.com/new (name `StudentRecordManagement`, **do not** add a README or .gitignore there). Then:

```
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/StudentRecordManagement.git
git push -u origin main
```

GitHub asks you to sign in through the browser (Git Credential Manager) or use a personal access token as the password. Later changes: `git add .`, `git commit -m "message"`, `git push`.

## Testing checklist

Local first, then repeat every row on the AWS public IP.

| # | Test | Expected result |
|---|---|---|
| 1 | Open the dashboard | Total, per-department counts and recent students appear |
| 2 | Add a student with valid data | Green success message; student appears in the list |
| 3 | Submit the add form with empty fields | Red messages for each missing field; nothing saved |
| 4 | Add a student with an existing roll number | Red "already exists" message; no second row |
| 5 | Enter an invalid email or a 5-digit phone | Validation message |
| 6 | View all students | Responsive table; shrink the window to check mobile layout |
| 7 | Search by name, roll number, department | Only matching rows; "No students match" for nonsense text |
| 8 | Edit a student and save | Success message; changes visible |
| 9 | Edit a student and use another student's roll number | Error; record unchanged |
| 10 | Delete: click Cancel, then repeat and click OK | Cancel keeps the row; OK deletes it with a message |
| 11 | Delete all rows (or search for something empty) | Friendly empty-state message |
| 12 | Stop MySQL (`net stop MySQL80`) and reload the site | "Database unavailable" page, no stack trace; restart MySQL and it recovers |
| 13 | AWS: restart the app (`sudo systemctl restart studentapp`) | Records are still there |
| 14 | AWS: query RDS from EC2 with the `mysql` client | The rows you added in the browser are in the `students` table |
| 15 | AWS: restart the EC2 instance | App starts by itself and the data is still there |

## Project explanation (for your report)

The system is a three-layer web application. The browser sends requests to Flask routes in `app.py`. Each route validates input, then runs a parameterized SQL query through the helper in `db.py` against MySQL. Flask renders the result with Jinja2 templates styled by Bootstrap 5. Database settings live in environment variables (`.env`), so the same code runs against local MySQL or Amazon RDS. For production, Gunicorn runs the Flask app as a managed service (`systemd`) and Nginx forwards public port 80 to it. Moving the database to RDS adds backups, patching and a managed server, and keeping the database off the public internet reduces the attack surface.

Security measures: parameterized queries, server-side validation, a CSRF token on every POST form, Jinja auto-escaping against XSS, a least-privilege MySQL user, and no secrets in Git.

## Viva questions and answers

**1. What is Flask?** A lightweight Python web framework. It maps URLs to Python functions (routes) and renders HTML templates.

**2. Why did you use `db.py` and a `.env` file?** To keep credentials out of the source code and out of GitHub. Changing `DB_HOST` is enough to switch from local MySQL to RDS.

**3. What is SQL injection and how does your project prevent it?** An attacker puts SQL code into an input field. I use parameterized queries (`%s` placeholders with values passed separately), so input is always treated as data, never as SQL.

**4. Why a separate MySQL user instead of root?** Least privilege: if the app is compromised, the attacker only gets `SELECT/INSERT/UPDATE/DELETE` on one database, not control of the whole server.

**5. How do you prevent duplicate roll numbers?** The column has a `UNIQUE` key in MySQL, and the app catches the duplicate-entry error (1062) and shows a friendly message. The database enforces it even if two users submit at once.

**6. Why Gunicorn if Flask has its own server?** Flask's built-in server is for development only. Gunicorn is a production WSGI server that handles several requests with multiple workers.

**7. What does Nginx do here?** It is a reverse proxy: it receives requests on port 80 and forwards them to Gunicorn on `127.0.0.1:8000`, so Gunicorn is never exposed directly.

**8. What does `systemd` do?** It starts Gunicorn at boot, restarts it if it crashes, and lets me manage it with `systemctl` and read logs with `journalctl`.

**9. What is Amazon EC2? What is Amazon RDS?** EC2 is a virtual server I manage myself (hosts the app). RDS is a managed database service: AWS handles installation, patching and backups.

**10. Why should RDS not be publicly accessible?** A public database can be attacked from anywhere. Here only the EC2 security group may connect on port 3306.

**11. What is a security group?** A virtual firewall for an AWS resource. Inbound rules list the allowed port, protocol and source.

**12. What is CSRF?** A malicious site tricks a logged-in browser into submitting a request. The hidden token in each form must match the session, so forged requests are rejected.

**13. What happens if the database is down?** The app catches the connector error, logs the details on the server and shows a "Database unavailable" page without exposing internal information.

**14. How do you know the data is really stored in RDS?** I connect to the RDS endpoint with the `mysql` client from EC2 and run `SELECT * FROM students;`, and the data survives app and instance restarts.

**15. Which AWS resources can cost money?** EC2 instance hours, EBS storage, the public IPv4 address, the RDS instance, its storage and backups. I delete them when the demo is finished.
