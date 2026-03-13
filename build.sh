#!/usr/bin/env bash
pip install -r requirements.txt
curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o $HOME/yt-dlp
chmod +x $HOME/yt-dlp
