import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from werkzeug.utils import secure_filename
from openai import OpenAI
from googleapiclient.discovery import build

load_dotenv()

app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///answers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ✅ OpenAI client initialization (no api_key manually)
client = OpenAI()

# ✅ YouTube API key from environment
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

class QA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, unique=True, nullable=False)
    answer = db.Column(db.Text, nullable=False)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/chat')
def chat():
    if 'messages' not in session:
        session['messages'] = []
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat_post():
    user_input = request.form.get('user_input')
    if not user_input and 'image' not in request.files:
        return jsonify({'reply': "❗ No input received.", 'youtube_embed': None})

    # Handle OCR image input
    if 'image' in request.files and request.files['image'].filename != '':
        image = request.files['image']
        filename = secure_filename(image.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(filepath)
        img = Image.open(filepath)
        user_input = pytesseract.image_to_string(img)
        if not user_input.strip():
            user_input = "❗ Could not read the image clearly. Please try again."

    # Save student's message instantly
    session['messages'].append({"role": "user", "content": user_input})

    # Check if question already stored
    existing = QA.query.filter_by(question=user_input).first()
    if existing:
        assistant_reply = existing.answer
        session['messages'].append({"role": "assistant", "content": assistant_reply})
    else:
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=session['messages']
            )
            assistant_reply = response.choices[0].message.content
            session['messages'].append({"role": "assistant", "content": assistant_reply})

            # Save to database
            new_qa = QA(question=user_input, answer=assistant_reply)
            db.session.add(new_qa)
            db.session.commit()
        except Exception as e:
            print(f"GPT Error: {e}")
            return jsonify({'reply': "❗ Error. Please try again.", 'youtube_embed': None})

    # Fetch related YouTube video
    youtube_embed = fetch_youtube_video(user_input)

    return jsonify({'reply': assistant_reply, 'youtube_embed': youtube_embed})

def fetch_youtube_video(query):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request = youtube.search().list(
            part='snippet',
            q=query,
            maxResults=1,
            type='video'
        )
        response = request.execute()
        video_id = response['items'][0]['id']['videoId']
        embed_url = f"https://www.youtube.com/embed/{video_id}"
        return embed_url
    except Exception as e:
        print(f"YouTube fetch error: {e}")
        return None

@app.route('/clear', methods=['POST'])
def clear():
    session.pop('messages', None)
    return redirect(url_for('chat'))

@app.route('/admin')
def admin():
    qas = QA.query.all()
    return render_template('admin.html', qas=qas)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        question = request.form['question']
        answer = request.form['answer']
        new_qa = QA(question=question, answer=answer)
        db.session.add(new_qa)
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('add.html')

@app.route('/edit/<int:qa_id>', methods=['GET', 'POST'])
def edit(qa_id):
    qa = QA.query.get_or_404(qa_id)
    if request.method == 'POST':
        qa.question = request.form['question']
        qa.answer = request.form['answer']
        db.session.commit()
        return redirect(url_for('admin'))
    return render_template('edit_question.html', qa=qa)

@app.route('/delete/<int:qa_id>')
def delete(qa_id):
    qa = QA.query.get_or_404(qa_id)
    db.session.delete(qa)
    db.session.commit()
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)), debug=True)
