FROM python:3.12-slim

WORKDIR /app

# 依存パッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリ本体をコピー
COPY . .

# データ保存ディレクトリを作成
RUN mkdir -p /data

EXPOSE 5000

CMD ["python", "run.py"]
