from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess, shutil, os

app = Flask(__name__)
CORS(app, origins="*")

@app.route('/audio')
def get_audio():
    vid = request.args.get('v', '').strip()
    if not vid or len(vid) > 20:
        return jsonify({'error': 'Invalid video ID'}), 400
    ytdlp = shutil.which('yt-dlp')
    if not ytdlp:
        return jsonify({'error': 'yt-dlp not found'}), 500
    try:
        result = subprocess.run(
            [ytdlp, '--no-playlist', '-f', 'bestaudio', '-g',
             f'https://youtube.com/watch?v={vid}'],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip().split('\n')[0]
        if not url:
            return jsonify({'error': 'No URL returned'}), 500
        return jsonify({'url': url})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/ping')
def ping():
    return 'pong'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
