#!/bin/bash

if ! docker image inspect navy > /dev/null 2>&1; then
  echo "🔧 Image 'navy' tidak ditemukan. Membangun image terlebih dahulu..."
  docker build . -t navy
  if [ $? -ne 0 ]; then
    echo "❌ Gagal membangun image 'navy'."
    exit 1
  fi
  echo "✅ Image 'navy' berhasil dibangun."
else
  echo "✅ Image 'navy' sudah ada."
fi

PORT=$(python3 -c "
import socket
p = next((p for p in range(7860, 7960) if socket.socket().connect_ex(('localhost', p)) != 0), None)
print(p)
")

if [ -z "$PORT" ]; then
  echo "❌ Tidak ada port kosong antara 7860-7959. Gagal menjalankan."
  exit 1
fi

echo "✅ Port kosong ditemukan: $PORT"

docker run --name navy -p ${PORT}:${PORT} -d -t navy

echo "🚀 Container 'navy' sudah jalan di port ${PORT}"
