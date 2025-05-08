# (内容は変更なし)
# Python ベースイメージを指定
FROM python:3.11-slim

# 環境変数設定
ENV PYTHONUNBUFFERED=1 \
    # Streamlit が利用するポート (Cloud Run は 8080 を想定)
    PORT=8080 \
    # タイムゾーン設定 (必要に応じて)
    TZ=Asia/Tokyo

# 作業ディレクトリを設定
WORKDIR /app

# Streamlit アプリの依存関係をコピーしてインストール
COPY ./streamlit_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Streamlit アプリケーションコードをコピー (app ディレクトリ全体をコピー)
COPY ./streamlit_app /app/streamlit_app
# (オプション) 静的ファイルがある場合
# COPY ./streamlit_app/static /app/streamlit_app/static

# ポートを公開 (Cloud Run 用)
EXPOSE 8080

# アプリケーションを実行 (パスを修正)
# python -m streamlit run ... でモジュールとして実行
CMD ["python", "-m", "streamlit", "run", "streamlit_app/main.py", "--server.port=8080", "--server.address=0.0.0.0"]
