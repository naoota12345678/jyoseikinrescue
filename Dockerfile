FROM python:3.11-slim

WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのコードをコピー
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/
# 助成金関連のドキュメントをコピー
COPY *.txt ./

# 非root用のユーザーを作成
RUN useradd --create-home --shell /bin/bash app
USER app

# ポートを公開
EXPOSE 8080

# アプリケーションを実行
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "src.app:app"]