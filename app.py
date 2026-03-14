from flask import Flask, jsonify, request
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app, origins="*")

@app.route('/audio')
def get_audio():
    vid = request.args.get('v', '').strip()
    if not vid or len(vid) > 20:
        return jsonify({'error': 'Invalid video ID'}), 400
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f'https://youtube.com/watch?v={vid}', download=False)
            url = info['url']
            if not url:
                return jsonify({'error': 'No URL returned'}), 500
            return jsonify({'url': url})
    except Exception as e:
        return jsonify({'error': str(e)[:300]}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
