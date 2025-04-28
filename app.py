from flask import Flask, render_template, request, jsonify, session
from openai import OpenAI
import pytesseract
from PIL import Image
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/save_profile', methods=['POST'])
def save_profile():
    """Save student's Board, Class, Subject in session."""
    session['student_board'] = request.form.get('board', 'CBSE')
    session['student_class'] = request.form.get('class', 'Class 8')
    session['student_subject'] = request.form.get('subject', 'Math')
    return jsonify({'status': 'success'})

@app.route('/chat', methods=['POST'])
def chat():
    final_prompt = ""

    user_input = ''
    if 'userInput' in request.form:
        user_input = request.form.get('userInput', '').strip()
    else:
        user_input_list = request.form.getlist('userInput')
        if user_input_list:
            user_input = user_input_list[0].strip()

    uploaded_file = None
    if 'cameraInput' in request.files and request.files['cameraInput'].filename != '':
        uploaded_file = request.files['cameraInput']
    elif 'galleryInput' in request.files and request.files['galleryInput'].filename != '':
        uploaded_file = request.files['galleryInput']

    ocr_text = ""
    if uploaded_file:
        try:
            image = Image.open(uploaded_file.stream)
            image = image.convert('RGB')
            image.thumbnail((1024, 1024))
            ocr_text = pytesseract.image_to_string(image)
        except Exception as e:
            print(f"OCR Error: {e}")

    # 🧠 Attach Student Profile info
    student_profile = f"You are a helpful AI tutor for a student studying {session.get('student_subject', 'Math')} for {session.get('student_board', 'CBSE')} Board in {session.get('student_class', 'Class 8')}. Reply in simple and clear way."

    if ocr_text.strip():
        final_prompt += f"OCR Extracted Text:\n{ocr_text.strip()}\n\n"
    if user_input.strip():
        final_prompt += f"{user_input.strip()}"

    final_prompt = student_profile + "\n\n" + final_prompt

    if not final_prompt:
        return jsonify({'reply': "⚠️ No input received.", 'youtube_embed': None})

    if 'messages' not in session:
        session['messages'] = []

    session['messages'].append({"role": "user", "content": str(final_prompt)})
    session['messages'] = session['messages'][-20:]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=session['messages']
        )
        assistant_reply = response.choices[0].message.content
        session['messages'].append({"role": "assistant", "content": str(assistant_reply)})
    except Exception as e:
        print(f"GPT Error: {e}")
        return jsonify({'reply': "❗Error. Please try again.", 'youtube_embed': None})

    youtube_embed = get_youtube_embed(final_prompt)

    return jsonify({'reply': assistant_reply, 'youtube_embed': youtube_embed})

def get_youtube_embed(query):
    api_key = os.getenv("YOUTUBE_API_KEY")
    search_url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        'part': 'snippet',
        'q': query,
        'key': api_key,
        'maxResults': 1,
        'type': 'video',
        'videoEmbeddable': 'true',
        'safeSearch': 'strict'
    }

    try:
        response = requests.get(search_url, params=params)
        results = response.json()
        if 'items' in results and len(results['items']) > 0:
            video_id = results['items'][0]['id']['videoId']
            return f"https://www.youtube.com/embed/{video_id}"
        else:
            return None
    except Exception as e:
        print(f"YouTube API error: {e}")
        return None

if __name__ == "__main__":
    app.run(debug=True)
