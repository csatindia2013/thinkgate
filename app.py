from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import openai
import pytesseract
from PIL import Image
import os
import requests
import sqlite3
from functools import wraps
import math
import re
from sympy import symbols, Eq, solve
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ✅ Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_URL = f"https://graph.facebook.com/v17.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "my_secure_token")

DB_FILE = 'questions.db'


def normalize(text):
    return re.sub(r'\s+', ' ', text.lower().strip())


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                normalized_question TEXT,
                answer TEXT,
                youtube TEXT
            )
        """)


init_db()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    error = ""
    if request.method == 'POST':
        if request.form.get('username') == 'admin' and request.form.get('password') == 'pass123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid credentials"
    return render_template('login.html', error=error)


@app.route('/admin/logout')
@login_required
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    search = request.args.get('search', '').strip()
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        if search:
            questions = conn.execute("SELECT * FROM questions WHERE question LIKE ? ORDER BY id DESC", (f"%{search}%",)).fetchall()
        else:
            questions = conn.execute("SELECT * FROM questions ORDER BY id DESC LIMIT 10").fetchall()
    return render_template('admin.html', questions=questions, search=search)


@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def add_question():
    if request.method == 'POST':
        q = request.form.get('question')
        a = request.form.get('answer')
        y = request.form.get('youtube')
        norm_q = normalize(q)
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO questions (question, normalized_question, answer, youtube) VALUES (?, ?, ?, ?)", (q, norm_q, a, y))
        return redirect(url_for('admin_dashboard'))
    return render_template('add.html')


@app.route('/admin/edit/<int:question_id>', methods=['GET', 'POST'])
@login_required
def edit_question(question_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        if request.method == 'POST':
            new_q = request.form.get('question')
            new_a = request.form.get('answer')
            new_y = request.form.get('youtube')
            norm_q = normalize(new_q)
            conn.execute("UPDATE questions SET question=?, normalized_question=?, answer=?, youtube=? WHERE id=?", (new_q, norm_q, new_a, new_y, question_id))
            return redirect(url_for('admin_dashboard'))
        question = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    return render_template('edit_question.html', question=question)


@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.form.get('userInput', '').strip()
        uploaded_file = request.files.get('cameraInput') or request.files.get('galleryInput')
        ocr_text = ""
        if uploaded_file:
            try:
                image = Image.open(uploaded_file.stream).convert('RGB')
                image.thumbnail((1024, 1024))
                ocr_text = pytesseract.image_to_string(image).strip()
            except Exception as e:
                print(f"❌ OCR Error: {e}")
                return jsonify({'reply': "❌ Error processing image. Please try again.", 'youtube_embed': ""}), 500
        final_prompt = f"{ocr_text}\n\n{user_input}".strip()
        if not final_prompt:
            return jsonify({'reply': "⚠️ No input received. Please try again.", 'youtube_embed': ""}), 400
        normalized_prompt = normalize(final_prompt)
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute("SELECT answer, youtube FROM questions WHERE normalized_question = ?", (normalized_prompt,)).fetchone()
            if existing:
                return jsonify({'reply': existing['answer'] or "(No answer available)", 'youtube_embed': existing['youtube'] or ""})
        if 'messages' not in session:
            session['messages'] = [{"role": "system", "content": "You are a helpful AI tutor for students. If the user's query involves any mathematical expression, equation, or calculation, always reply using LaTeX formatting inside $$ symbols."}]
        session['messages'].append({"role": "user", "content": final_prompt})
        session['messages'] = session['messages'][-20:]
        response = openai.ChatCompletion.create(model="gpt-4o", messages=session['messages'])
        assistant_reply = response.choices[0].message.content.strip()
        youtube_embed = get_youtube_embed(final_prompt)
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO questions (question, normalized_question, answer, youtube) VALUES (?, ?, ?, ?)", (final_prompt, normalized_prompt, assistant_reply, youtube_embed))
        return jsonify({'reply': assistant_reply, 'youtube_embed': youtube_embed or ""})
    except Exception as e:
        print(f"❌ Chat Processing Error: {e}")
        return jsonify({'reply': "❌ An error occurred. Please try again.", 'youtube_embed': ""}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
