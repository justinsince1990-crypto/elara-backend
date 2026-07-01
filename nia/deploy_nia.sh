#!/bin/bash

echo "🚀 Starting deployment for Nia (The Way)..."

cd /root/elara || { echo "Directory not found"; exit 1; }

# Pull latest changes (uncomment if using git pull)
# git pull origin main

# Update dependencies if needed
# /root/elara/venv/bin/pip install -r requirements.txt

echo "🌱 Restarting Nia service..."
systemctl restart nia

echo "✅ Deployment complete! Nia is live on port 8002."
