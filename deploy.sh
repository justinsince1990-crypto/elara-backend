#!/bin/bash

echo "🚀 Starting deployment for Project Elara..."

cd /root/elara || { echo "Directory not found"; exit 1; }

# 1. Pull latest changes (Remove the '#' if using git)
# git pull origin main

# 2. Update dependencies (Remove the '#' if updating requirements)
# /root/elara/venv/bin/pip install -r requirements.txt

echo "🌱 Restarting Elara service..."
systemctl restart elara

echo "✅ Deployment complete! Elara is live."
