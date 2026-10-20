"""Database connection module.

All connection settings come from environment variables (loaded from a .env
file during development). Switching from local MySQL to Amazon RDS only
requires changing DB_HOST (and the credentials) in .env - no code changes.
"""
import os

import mysql.connector
from dotenv import load_dotenv

# Load .env from the same folder as this file, regardless of where the app is started.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def get_connection():
    """Open and return a new MySQL connection.

    Raises mysql.connector.Error if the server cannot be reached or the
    credentials are wrong; the caller (app.py) handles that error.
    """
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "student_management"),
        charset="utf8mb4",
        connection_timeout=5,
    )
