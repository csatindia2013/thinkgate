from flask import Flask, render_template, request, jsonify, session
import openai
import pytesseract
from PIL import Image
import os
import requests

# ✅ Flask App
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# ✅ Get OpenAI API Key from Render's environment
openai.api_key = os.getenv("OPENAI_API_KEY")

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    final_prompt = ""

    # Get user text input
    user_input = request.form.get('userInput', '').strip()

    # Get uploaded image (camera or gallery)
    uploaded_file = request.files.get('cameraInput') or request.files.get('galleryInput')

    ocr_text = ""
    if uploaded_file:
        try:
            image = Image.open(uploaded_file.stream).convert('RGB')
            image.thumbnail((1024, 1024))
            ocr_text = pytesseract.image_to_string(image)
        except Exception as e:
            print("❌ OCR Error:", e)

    if ocr_text.strip():
        final_prompt += f"OCR Extracted Text:\n{ocr_text.strip()}\n\n"
    if user_input:
        final_prompt += user_input

    if not final_prompt.strip():
        return jsonify({'reply': "⚠️ No input received.", 'youtube_embed': None})

    if 'messages' not in session:
        session['messages'] = [{
            "role": "system",
            "content": "You are a helpful AI tutor for students. If the user's query involves math or science, explain using LaTeX formatting inside $$ symbols."
        }]

    session['messages'].append({"role": "user", "content": final_prompt.strip()})
    session['messages'] = session['messages'][-20:]  # keep context short

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=session['messages']
        )
        assistant_reply = response.choices[0].message.content.strip()
        session['messages'].append({"role": "assistant", "content": assistant_reply})
    except Exception as e:
        import traceback
        print("❌ GPT Exception:", e)
        traceback.print_exc()
        return jsonify({'reply': "❗ Error processing your request. Please try again.", 'youtube_embed': ""}), 500

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

        if 'items' in results and results['items']:
            video_id = results['items'][0]['id']['videoId']
            return f"https://www.youtube.com/embed/{video_id}"
    except Exception as e:
        print("❌ YouTube API Error:", e)

    return None

# ✅ For Render deployment (bind to 0.0.0.0 and dynamic port)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
