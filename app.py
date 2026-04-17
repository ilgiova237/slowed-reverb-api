import os
import subprocess
import shutil
import re
import urllib.request
import urllib.error
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")

COOKIES_SRC = "/etc/secrets/cookies.txt"
COOKIES_DST = "/tmp/cookies.txt"
YTDLP_PATH = "/tmp/yt-dlp"
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"

# ── yt-dlp setup ──────────────────────────────────────────────────────────────

def ensure_ytdlp():
    if not os.path.exists(YTDLP_PATH):
        print("[yt-dlp] Downloading latest binary...")
        try:
            urllib.request.urlretrieve(YTDLP_URL, YTDLP_PATH)
            os.chmod(YTDLP_PATH, 0o755)
            print("[yt-dlp] Download complete")
        except Exception as e:
            print(f"[yt-dlp] Download failed: {e}")

def get_ytdlp():
    if os.path.exists(YTDLP_PATH):
        return YTDLP_PATH
    return shutil.which("yt-dlp")

ensure_ytdlp()

# ── Cookies ───────────────────────────────────────────────────────────────────

def prepare_cookies():
    if os.path.exists(COOKIES_SRC):
        try:
            shutil.copy2(COOKIES_SRC, COOKIES_DST)
            return True
        except Exception:
            return False
    return False

# ── CORS ──────────────────────────────────────────────────────────────────────

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, HEAD"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Accept, Origin, X-Requested-With, Range"
    )
    response.headers["Access-Control-Expose-Headers"] = (
        "Content-Length, Content-Range, Content-Type, Accept-Ranges"
    )
    return response

# ── yt-dlp extraction ─────────────────────────────────────────────────────────

def get_audio_url(video_id, use_cookies=False, extra_args=None):
    ytdlp = get_ytdlp()
    if not ytdlp:
        return None, "yt-dlp not found"

    cmd = [
        ytdlp,
        "--no-playlist",
        "--format", "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
        "--get-url",
        "--no-warnings",
        "--no-check-certificates",
        "--extractor-retries", "3",
        "--socket-timeout", "30",
        "--user-agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36",
    ]

    if use_cookies and os.path.exists(COOKIES_DST):
        cmd.extend(["--cookies", COOKIES_DST])
    if extra_args:
        cmd.extend(extra_args)

    cmd.append(f"https://www.youtube.com/watch?v={video_id}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0 and stdout:
            lines = [l.strip() for l in stdout.splitlines()
                     if l.strip().startswith("http")]
            if lines:
                return lines[0], None
            return None, f"No valid URL in output: {stdout[:100]}"

        return None, stderr or f"yt-dlp exit code {result.returncode}"

    except subprocess.TimeoutExpired:
        return None, "yt-dlp timed out"
    except Exception as e:
        return None, str(e)


def extract_audio_url(video_id):
    if not re.match(r'^[A-Za-z0-9_-]{6,15}$', video_id):
        return None, "Invalid video ID", None

    prepare_cookies()

    strategies = [
        {"name": "default",     "use_cookies": False, "extra_args": []},
        {"name": "cookies",     "use_cookies": True,  "extra_args": []},
        {"name": "android",     "use_cookies": False,
         "extra_args": ["--extractor-args", "youtube:player_client=android"]},
        {"name": "ios",         "use_cookies": False,
         "extra_args": ["--extractor-args", "youtube:player_client=ios"]},
        {"name": "tv_embedded", "use_cookies": False,
         "extra_args": ["--extractor-args",
                        "youtube:player_client=tv_embedded"]},
    ]

    last_error = "All strategies failed"
    for s in strategies:
        if s["use_cookies"] and not os.path.exists(COOKIES_DST):
            continue
        url, error = get_audio_url(
            video_id, s["use_cookies"], s["extra_args"]
        )
        if url:
            return url, None, s["name"]
        last_error = error
        print(f"[extract] Strategy '{s['name']}' failed: {error}")

    return None, last_error, None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/ping", methods=["GET", "HEAD", "OPTIONS"])
def ping():
    if request.method == "OPTIONS":
        return Response("", status=204)

    ytdlp = get_ytdlp()
    version = "unknown"
    if ytdlp:
        try:
            v = subprocess.run(
                [ytdlp, "--version"],
                capture_output=True, text=True, timeout=5
            )
            version = v.stdout.strip()
        except Exception:
            pass

    return jsonify({
        "status": "ok",
        "message": "pong",
        "ytdlp_ok": ytdlp is not None,
        "ytdlp_version": version,
        "cookies": os.path.exists(COOKIES_SRC),
    })


@app.route("/audio", methods=["GET", "OPTIONS"])
def audio():
    """
    Proxy endpoint — streams YouTube audio through this server.
    Browser fetches /audio?v=ID from here, never touches googlevideo.com.
    """
    if request.method == "OPTIONS":
        return Response("", status=204)

    video_id = request.args.get("v", "").strip()
    if not video_id:
        return jsonify({"error": "Missing ?v=VIDEO_ID"}), 400

    yt_url, error, strategy = extract_audio_url(video_id)
    if not yt_url:
        return jsonify({"error": error, "video_id": video_id}), 500

    print(f"[proxy] Streaming {video_id} strategy={strategy}")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.youtube.com/",
            "Origin": "https://www.youtube.com",
        }

        range_header = request.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        req = urllib.request.Request(yt_url, headers=headers)
        upstream = urllib.request.urlopen(req, timeout=30)

        upstream_status  = upstream.status
        content_type     = upstream.headers.get("Content-Type", "audio/mp4")
        content_length   = upstream.headers.get("Content-Length")
        content_range    = upstream.headers.get("Content-Range")
        accept_ranges    = upstream.headers.get("Accept-Ranges", "bytes")

        CHUNK = 65536

        def generate():
            try:
                while True:
                    chunk = upstream.read(CHUNK)
                    if not chunk:
                        break
                    yield chunk
            except Exception as e:
                print(f"[proxy] Stream error: {e}")
            finally:
                upstream.close()

        resp_headers = {
            "Content-Type":                content_type,
            "Accept-Ranges":               accept_ranges,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control":               "no-cache",
            "X-Strategy":                  strategy or "unknown",
        }
        if content_length:
            resp_headers["Content-Length"] = content_length
        if content_range:
            resp_headers["Content-Range"]  = content_range

        status_code = 206 if upstream_status == 206 else 200

        return Response(
            stream_with_context(generate()),
            status=status_code,
            headers=resp_headers,
            direct_passthrough=True,
        )

    except urllib.error.HTTPError as e:
        return jsonify({
            "error": f"Upstream HTTP {e.code} — stream URL may have expired, retry.",
            "video_id": video_id,
        }), 502

    except urllib.error.URLError as e:
        return jsonify({
            "error": f"Could not reach audio source: {e.reason}",
            "video_id": video_id,
        }), 502

    except Exception as e:
        return jsonify({
            "error": f"Proxy error: {str(e)}",
            "video_id": video_id,
        }), 500


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found",
                    "endpoints": ["/ping", "/audio?v=VIDEO_ID"]}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error", "detail": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
