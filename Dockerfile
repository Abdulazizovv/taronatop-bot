# 1. Python 3.12 slim image bazasida
FROM python:3.12-slim

# 2. Ishchi katalogni o'rnatish
WORKDIR /usr/src/app

# 3. .pyc fayllarni yozishni oldini olish, loglar real vaqt ko'rinishida
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 4. Tizimga kerakli paketlarni o‘rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 5. pip yangilash
RUN pip install --upgrade pip

# 6. Talablar faylini nusxalash va o‘rnatish
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 7. Loyihani konteynerga nusxalash
COPY . .

