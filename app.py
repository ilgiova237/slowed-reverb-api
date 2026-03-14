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

    po_token = os.environ.get('PO_TOKEN')
    cookies = get_cookies_path()

    # Try multiple strategies
    strategies = [
        # Strategy 1: no format specified, no cookies
        {'quiet': True, 'no_warnings': True},
        # Strategy 2: no format, with cookies
        {'quiet': True, 'no_warnings': True, 'cookiefile': cookies} if cookies else None,
        # Strategy 3: worst format (most compatible)
        {'quiet': True, 'no_warnings': True, 'format': 'worstaudio/worst'},
    ]

    for opts in strategies:
        if opts is None:
            continue
        if po_token:
            opts.setdefault('extractor_args', {})
            opts['extractor_args']['youtube'] = {'player_client': ['web'], 'po_token': [f'web+{po_token}']}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f'https://youtube.com/watch?v={vid}', download=False)
                formats = info.get('formats', [])
                # Get best audio-only
                audio = [f for f in formats if f.get('vcodec') == 'none' and f.get('url') and f.get('acodec') != 'none']
                if audio:
                    best = sorted(audio, key=lambda x: x.get('abr') or 0, reverse=True)[0]
                    return jsonify({'url': best['url']})
                # Fallback: direct url from info
                if info.get('url'):
                    return jsonify({'url': info['url']})
        except Exception:
            continue

    return jsonify({'error': 'Could not extract audio from this video'}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
