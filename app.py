from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import os
import shutil

app = Flask(__name__)
CORS(app, origins="*")

COOKIES_SRC = '/etc/secrets/cookies.txt'
COOKIES_DST = '/tmp/cookies.txt'

def get_cookies_path():
    if os.path.exists(COOKIES_SRC):
        shutil.copy2(COOKIES_SRC, COOKIES_DST)
        os.chmod(COOKIES_DST, 0o600)
        return COOKIES_DST
    return None

@app.route('/audio')
def get_audio():
    vid = request.args.get('v', '').strip()
    if not vid or len(vid) > 20:
        return jsonify({'error': 'Invalid video ID'}), 400
    
    cookies = get_cookies_path()
    
    # Try multiple format combinations
    attempts = [
        {'format': '140'},   # m4a 128kbps - most compatible
        {'format': '251'},   # webm opus 128kbps
        {'format': '139'},   # m4a 48kbps
        {'format': '249'},   # webm opus 48kbps
        {'format': '18'},    # mp4 360p with audio fallback
    ]
    
    last_error = None
    for attempt in attempts:
        try:
            opts = {
                'quiet': True,
                'no_warnings': True,
                'format': attempt['format'],
            }
            if cookies:
                opts['cookiefile'] = cookies
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f'https://youtube.com/watch?v={vid}', download=False)
                url = info.get('url') or (info.get('formats') or [{}])[-1].get('url')
                if url:
                    return jsonify({'url': url})
        except Exception as e:
            last_error = str(e)[:200]
            continue
    
    return jsonify({'error': last_error or 'No format worked'}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
