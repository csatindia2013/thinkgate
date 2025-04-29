from flask import Flask, render_template, request, jsonify, session
import openai
import pytesseract
from PIL import Image
import os
from dotenv import load_dotenv
import requests

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    final_prompt = ""

    # ✅ Extract user input text
    user_input = request.form.get('userInput', '').strip()

    # ✅ Extract uploaded file (camera or gallery)
    uploaded_file = None
    if 'cameraInput' in request.files and request.files['cameraInput'].filename:
        uploaded_file = request.files['cameraInput']
    elif 'galleryInput' in request.files and request.files['galleryInput'].filename:
        uploaded_file = request.files['galleryInput']

    # ✅ Perform OCR if image exists
    ocr_text = ""
    if uploaded_file:
        try:
            image = Image.open(uploaded_file.stream).convert('RGB')
            image.thumbnail((1024, 1024))
            ocr_text = pytesseract.image_to_string(image)
        except Exception as e:
            print(f"OCR Error: {e}")

    # ✅ Combine prompt
    if ocr_text.strip():
        final_prompt += f"OCR Extracted Text:\n{ocr_text.strip()}\n\n"
    if user_input:
        final_prompt += user_input

    final_prompt = final_prompt.strip()
    if not final_prompt:
        return jsonify({'reply': "⚠️ No input received.", 'youtube_embed': ""})

    # ✅ Initialize chat history
    if 'messages' not in session:
        session['messages'] = [{
            "role": "system",
            "content": "You are a helpful AI tutor for students. If the user's query involves any mathematical expression, equation, or calculation, always reply using LaTeX formatting inside $$ symbols."
        }]

    session['messages'].append({"role": "user", "content": final_prompt})
    session['messages'] = session['messages'][-20:]  # keep last 20

    # ✅ Get GPT response
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=session['messages']
        )
        assistant_reply = response.choices[0].message.content.strip()
        session['messages'].append({"role": "assistant", "content": assistant_reply})
    except Exception as e:
        print(f"GPT Error: {e}")
        return jsonify({'reply': "❗ Error processing your request. Please try again.", 'youtube_embed': ""}), 500

    # ✅ Get YouTube video
    youtube_embed = get_youtube_embed(final_prompt)

    return jsonify({
        'reply': assistant_reply,
        'youtube_embed': youtube_embed or ""
    })

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
    app.run(debug=True)
