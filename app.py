import os
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import pytesseract
from PIL import Image
from werkzeug.utils import secure_filename
import openai
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///answers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# ✅ Correct way for OpenAI client
openai_client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# ✅ YouTube API Key
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Database model
class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(500))
    answer = db.Column(db.Text)

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_input = request.form.get('user_input')

        if not user_input.strip():
            return jsonify({'error': 'No input received.'})

        # Check database
        existing = Answer.query.filter_by(question=user_input).first()
        if existing:
            return jsonify({'response': existing.answer})

        # Prepare GPT prompt
        messages = [
            {"role": "system", "content": "You are a helpful academic tutor. Provide clear, student-friendly explanations. Format math answers in LaTeX if needed."},
            {"role": "user", "content": user_input}
        ]

        try:
            # GPT response
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5
            )

            gpt_reply = response.choices[0].message.content.strip()

            # Save to database
            new_entry = Answer(question=user_input, answer=gpt_reply)
            db.session.add(new_entry)
            db.session.commit()

            # Search YouTube
            youtube_video = search_youtube(user_input)

            return jsonify({'response': gpt_reply, 'video': youtube_video})

        except Exception as e:
            print("GPT Error:", str(e))
            return jsonify({'error': 'Error. Please try again.'})

    return render_template('chat.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return redirect(url_for('chat'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('chat'))

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        text = pytesseract.image_to_string(Image.open(filepath))

        return jsonify({'extracted_text': text})

@app.route('/admin', methods=['GET'])
def admin():
    entries = Answer.query.all()
    return render_template('admin.html', entries=entries)

def search_youtube(query):
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        req = youtube.search().list(q=query, part='snippet', type='video', maxResults=1)
        res = req.execute()
        video_id = res['items'][0]['id']['videoId']
        embed_link = f"https://www.youtube.com/embed/{video_id}"
        return embed_link
    except Exception as e:
        print("YouTube Error:", str(e))
        return None

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
