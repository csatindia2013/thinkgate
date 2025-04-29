from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import openai
import pytesseract
from PIL import Image
import os
import requests
import sqlite3
from functools import wraps
import math

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

openai.api_key = os.getenv("OPENAI_API_KEY")

DB_FILE = 'questions.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
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

@app.route('/admin/questions')
@login_required
def view_questions():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        total = cursor.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        questions = cursor.execute("SELECT * FROM questions ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    total_pages = math.ceil(total / per_page)
    return render_template('questions.html', questions=questions, page=page, total_pages=total_pages)

@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def add_question():
    if request.method == 'POST':
        q = request.form.get('question')
        a = request.form.get('answer')
        y = request.form.get('youtube')
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("INSERT INTO questions (question, answer, youtube) VALUES (?, ?, ?)", (q, a, y))
        return redirect(url_for('view_questions'))
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
            conn.execute("UPDATE questions SET question=?, answer=?, youtube=? WHERE id=?", (new_q, new_a, new_y, question_id))
            return redirect(url_for('view_questions'))
        question = conn.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone()
    return render_template('edit_question.html', question=question)

@app.route('/admin/cleared')
@login_required
def cleared_questions():
    return render_template('cleared.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    final_prompt = ""
    user_input = request.form.get('userInput', '').strip()
    uploaded_file = request.files.get('cameraInput') or request.files.get('galleryInput')
    ocr_text = ""

    if uploaded_file:
        try:
            image = Image.open(uploaded_file.stream).convert('RGB')
            image.thumbnail((1024, 1024))
            ocr_text = pytesseract.image_to_string(image)
        except Exception as e:
            print(f"OCR Error: {e}")

    if ocr_text.strip():
        final_prompt += f"OCR Extracted Text:\n{ocr_text.strip()}\n\n"
    if user_input:
        final_prompt += user_input

    if not final_prompt.strip():
        return jsonify({'reply': "⚠️ No input received.", 'youtube_embed': ""})

    with sqlite3.connect(DB_FILE) as conn:
        existing = conn.execute("SELECT answer, youtube FROM questions WHERE question = ?", (final_prompt.strip(),)).fetchone()

    if existing:
        return jsonify({
            'reply': existing[0] or "(No answer available)",
            'youtube_embed': existing[1] or ""
        })

    if 'messages' not in session:
        session['messages'] = [{
            "role": "system",
            "content": "You are a helpful AI tutor for students. If the user's query involves any mathematical expression, equation, or calculation, always reply using LaTeX formatting inside $$ symbols."
        }]

    session['messages'].append({"role": "user", "content": final_prompt.strip()})
    session['messages'] = session['messages'][-20:]

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=session['messages']
        )
        assistant_reply = response.choices[0].message.content.strip()
    except Exception as e:
        import traceback
        print("❌ GPT Error:", e)
        traceback.print_exc()
        return jsonify({'reply': "❗ Error processing your request. Please try again.", 'youtube_embed': ""}), 500

    youtube_embed = get_youtube_embed(final_prompt)

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT INTO questions (question, answer, youtube) VALUES (?, ?, ?)", (final_prompt.strip(), assistant_reply, youtube_embed))

    return jsonify({'reply': assistant_reply, 'youtube_embed': youtube_embed or ""})

def get_youtube_embed(query):
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return ""
    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                'part': 'snippet',
                'q': query,
                'key': api_key,
                'maxResults': 1,
                'type': 'video',
                'videoEmbeddable': 'true',
                'safeSearch': 'strict'
            }
        )
        data = response.json()
        if 'items' in data and len(data['items']) > 0:
            return f"https://www.youtube.com/embed/{data['items'][0]['id']['videoId']}"
        return ""
    except Exception as e:
        print(f"YouTube API error: {e}")
        return ""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
