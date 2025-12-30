#!/bin/bash
# Start Agno Multi-Agent Server

cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Start server
echo "🚀 Starting Agno Multi-Agent Server..."
python server.py




