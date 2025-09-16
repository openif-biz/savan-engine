FROM python:3.10-slim

WORKDIR /app

# 必要なPythonライブラリをインストール
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . /app

EXPOSE 8501

# 起動コマンドをテスト用に変更
CMD ["streamlit", "run", "test_app.py", "--server.port=8501", "--server.address=0.0.0.0"]