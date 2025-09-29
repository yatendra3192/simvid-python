#!/bin/bash

# Start the RQ worker in the background
echo "🚀 Starting RQ Worker..."
python worker.py &

# Start the web server (foreground)
echo "🌐 Starting Web Server..."
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-level info