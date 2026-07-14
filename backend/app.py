import os
import jwt
import bcrypt
import datetime
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from mysql.connector import Error as MySQLError

from db import get_connection

load_dotenv()

app = Flask(__name__)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
CORS(app, origins=CORS_ORIGINS, supports_credentials=True)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "12"))


# ---------- Helpers ----------

def make_token(user_id, username):
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated


# ---------- Routes ----------

@app.route("/api/health", methods=["GET"])
def health():
    # Useful for an ALB/ELB health check target group in AWS
    return jsonify({"status": "ok"}), 200


@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    if not username or not email or not password:
        return jsonify({"error": "username, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "password must be at least 6 characters"}), 400

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash),
        )
        conn.commit()
        user_id = cursor.lastrowid
        cursor.close()
        return jsonify({"message": "User registered successfully", "user_id": user_id}), 201
    except MySQLError as e:
        if e.errno == 1062:  # duplicate entry
            return jsonify({"error": "username or email already exists"}), 409
        return jsonify({"error": "database error", "detail": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s OR email = %s",
            (username, username),
        )
        user = cursor.fetchone()
        cursor.close()

        if not user or not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
            return jsonify({"error": "invalid username or password"}), 401

        token = make_token(user["id"], user["username"])
        return jsonify({"message": "Login successful", "token": token, "username": user["username"]}), 200
    except MySQLError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/api/me", methods=["GET"])
@token_required
def me():
    # A protected route to prove the token works end to end
    return jsonify({"user_id": request.user["user_id"], "username": request.user["username"]}), 200


@app.route("/api/notes", methods=["GET", "POST"])
@token_required
def notes():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            content = (data.get("content") or "").strip()
            if not content:
                return jsonify({"error": "content is required"}), 400
            cursor.execute(
                "INSERT INTO notes (user_id, content) VALUES (%s, %s)",
                (request.user["user_id"], content),
            )
            conn.commit()
            note_id = cursor.lastrowid
            return jsonify({"message": "Note created", "note_id": note_id}), 201

        cursor.execute(
            "SELECT id, content, created_at FROM notes WHERE user_id = %s ORDER BY created_at DESC",
            (request.user["user_id"],),
        )
        rows = cursor.fetchall()
        for r in rows:
            r["created_at"] = r["created_at"].isoformat()
        return jsonify({"notes": rows}), 200
    except MySQLError as e:
        return jsonify({"error": "database error", "detail": str(e)}), 500
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    # For local dev only. In production (EC2), run this behind gunicorn, e.g.:
    # gunicorn -w 3 -b 0.0.0.0:5000 app:app
    app.run(host="0.0.0.0", port=5000, debug=True)
