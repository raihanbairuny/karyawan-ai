#!/bin/bash
# Script untuk mendeploy Karyawan AI

echo "🚀 Memulai deployment Karyawan AI..."

# Pull kode terbaru
echo "📦 Mengambil update terbaru dari Git..."
git pull origin main

# Build ulang docker image (tanpa cache jika perlu, tapi untuk speed bisa dihilangkan)
echo "🐳 Membangun dan merestart container..."
docker compose build --no-cache
docker compose up -d

# Restart container dengan image baru tanpa downtime panjang
echo "🔄 Merestart services..."
docker compose up -d

echo "✅ Deployment selesai!"
