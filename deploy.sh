#!/bin/bash
# Script untuk mendeploy Karyawan AI
set -e

echo "🚀 Memulai deployment Karyawan AI..."

# Build & restart containers
echo "🐳 Membangun dan merestart container..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "✅ Deployment selesai!"
