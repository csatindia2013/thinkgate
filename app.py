from flask import Flask, render_template, request, jsonify, session
import openai
import pytesseract
from PIL import Image
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ✅ Correct OpenAI API key setting
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def index():
    return render_template('chat.html')

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

    if ocr_text.strip():
        final_prompt += f"OCR Extracted Text:\n{ocr_text.strip()}\n\n"
    if user_input.strip():
        final_prompt += f"{user_input.strip()}"

    final_prompt = final_prompt.strip()

    if not final_prompt:
        return jsonify({'reply': "⚠️ No input received.", 'youtube_embed': None})

    if 'messages' not in session:
        session['messages'] = []

    if len(session['messages']) == 0:
        session['messages'].append({
            "role": "system",
            "content": "You are a helpful AI tutor for students. If the user's query involves math, reply using LaTeX format between $$ $$ symbols."
        })

    session['messages'].append({"role": "user", "content": final_prompt})

    session['messages'] = session['messages'][-20:]

    try:
        # ✅ Correct OpenAI call
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=session['messages']
        )
        assistant_reply = response['choices'][0]['message']['content']

        session['messages'].append({"role": "assistant", "content": assistant_reply})

    except Exception as e:
        print(f"GPT Error: {e}")
        return jsonify({'reply': "❗Error. Please try again.", 'youtube_embed': None})

    youtube_embed = get_youtube_embed(final_prompt)

    return jsonify({'reply': assistant_reply, 'youtube_embed': youtube_embed})

def get_youtube_embed(query):
    """Search YouTube for a video matching the query and return embed link."""
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
        print(f"YouTube API Error: {e}")
        return None

if __name__ == "__main__":
    app.run(debug=True)
