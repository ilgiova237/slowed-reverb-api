from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess, shutil, os

app = Flask(__name__)
CORS(app, origins="*")

def find_ytdlp():
    # Check multiple possible locations
    locations = [
        shutil.which('yt-dlp'),
        '/opt/render/project/src/yt-dlp',
        os.path.join(os.path.expanduser('~'), 'yt-dlp'),
        '/tmp/yt-dlp',
        './yt-dlp',
    ]
    for p in locations:
        if p and os.path.exists(p):
            return p
    return None

@app.route('/audio')
def get_audio():
    vid = request.args.get('v', '').strip()
    if not vid or len(vid) > 20:
        return jsonify({'error': 'Invalid video ID'}), 400
    ytdlp = find_ytdlp()
    if not ytdlp:
        # List files to debug
        home = os.path.expanduser('~')
        files = os.listdir(home) if os.path.exists(home) else []
        return jsonify({'error': f'yt-dlp not found. HOME={home}, files={files}'}), 500
    try:
        result = subprocess.run(
            [ytdlp, '--no-playlist', '-f', 'bestaudio', '-g',
             f'https://youtube.com/watch?v={vid}'],
            capture_output=True, text=True, timeout=30
        )
        url = result.stdout.strip().split('\n')[0]
        if not url:
            return jsonify({'error': 'No URL returned', 'stderr': result.stderr[:200]}), 500
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
