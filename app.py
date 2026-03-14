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

def make_opts(cookies):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
    }
    if cookies:
        opts['cookiefile'] = cookies
    return opts

@app.route('/debug')
def debug():
    vid = request.args.get('v', 'dQw4w9WgXcQ').strip()
    cookies = get_cookies_path()
    opts = make_opts(cookies)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'https://youtube.com/watch?v={vid}', download=False)
            formats = info.get('formats', [])
            summary = [{'id': f.get('format_id'), 'ext': f.get('ext'), 'acodec': f.get('acodec'), 'vcodec': f.get('vcodec'), 'abr': f.get('abr'), 'url': bool(f.get('url'))} for f in formats[:20]]
            return jsonify({'count': len(formats), 'formats': summary})
    except Exception as e:
        return jsonify({'error': str(e)[:500]})

@app.route('/audio')
def get_audio():
    vid = request.args.get('v', '').strip()
    if not vid or len(vid) > 20:
        return jsonify({'error': 'Invalid video ID'}), 400
    cookies = get_cookies_path()
    opts = make_opts(cookies)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f'https://youtube.com/watch?v={vid}', download=False)
            formats = info.get('formats', [])
            audio = [f for f in formats if f.get('vcodec') == 'none' and f.get('url')]
            if audio:
                best = sorted(audio, key=lambda x: x.get('abr') or 0, reverse=True)[0]
                return jsonify({'url': best['url']})
            any_audio = [f for f in formats if f.get('acodec') not in (None, 'none') and f.get('url')]
            if any_audio:
                return jsonify({'url': any_audio[-1]['url']})
            return jsonify({'error': 'No audio format found'}), 500
    except Exception as e:
        return jsonify({'error': str(e)[:300]}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
