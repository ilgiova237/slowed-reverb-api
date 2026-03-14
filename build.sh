#!/usr/bin/env bash
pip install -r requirements.txt
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o ./yt-dlp
chmod +x ./yt-dlp
echo "yt-dlp saved to: $(pwd)/yt-dlp"
ls -la ./yt-dlp
