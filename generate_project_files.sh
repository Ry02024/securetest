#!/bin/bash
# generate_project_files.sh
# Usage: ./generate_project_files.sh <your-gcp-project-id>
# Generates the project file structure and initial code in the current directory.

# --- 引数から PROJECT_ID を取得 ---
if [[ $# -eq 0 ]]; then
  echo "エラー: 引数に GCP Project ID を指定してください。"
  echo "使用法: ./generate_project_files.sh <your-gcp-project-id>"
  exit 1
fi
export PROJECT_ID="$1" # export してサブシェルでも使えるようにする (必須ではないが一応)

# --- 自動取得 ---
echo "Using GCP Project ID from argument: ${PROJECT_ID}"
echo "プロジェクト番号を取得中..."
# gcloud コマンドが利用可能かチェック
if ! command -v gcloud &> /dev/null; then
    echo "エラー: gcloud コマンドが見つかりません。gcloud CLIがインストールされ、PATHが通っているか確認してください。"
    exit 1
fi
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)' 2>/dev/null)
if [[ -z "${PROJECT_NUMBER}" ]]; then
    echo "エラー: プロジェクト番号の取得に失敗しました。gcloud CLIが認証されているか、指定されたPROJECT_ID '${PROJECT_ID}' が正しいか確認してください。"
    # gcloud auth list # 認証状態の確認コマンド例 (必要ならコメント解除)
    exit 1
fi
echo "プロジェクト番号: ${PROJECT_NUMBER}"

# --- ディレクトリ作成 (カレントディレクトリ直下) ---
echo "ディレクトリ構造を作成中 (カレントディレクトリ直下)..."
mkdir -p .github/workflows \
           cloud_functions/chat_api \
           streamlit_app/core \
           streamlit_app/pages \
           streamlit_app/static
echo "ディレクトリ作成完了。"

# --- ファイル生成 (カレントディレクトリ直下) ---
echo "ファイルを作成し、コンテンツを書き込み中..."

# .gitignore
cat << 'EOGF' > .gitignore
# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
ENV/
pip-freeze.txt
pip-selfcheck.json
# IDE/Editor specific
.vscode/
.idea/
*.swp
*.swo
# Secrets / Config
streamlit_app/config.yaml
secrets/
.env
*.json
# OS specific
.DS_Store
Thumbs.db
# Terraform state files
*.tfstate
*.tfstate.backup
# Firebase cache/logs
.firebase/
firebase-debug.log
database-debug.log
firestore-debug.log
storage-debug.log
ui-debug.log
# Generated files
client_id.txt
client_secret.txt
EOGF

# .dockerignore
cat << 'EOGF' > .dockerignore
.git/
.gitignore
.dockerignore
README.md
streamlit_app/config.yaml
venv/
env/
.vscode/
__pycache__/
*.pyc
*.pyo
*.pyd
cloud_functions/
firestore.rules
firebase.json
*.sh
*.tfstate
*.tfstate.backup
.firebase/
*.log
client_id.txt
client_secret.txt
EOGF

# Dockerfile
cat << 'EOGF' > Dockerfile
# Python ベースイメージを指定
FROM python:3.11-slim
# 環境変数設定
ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    TZ=Asia/Tokyo
# 作業ディレクトリを設定
WORKDIR /app
# Streamlit アプリの依存関係をコピーしてインストール
COPY ./streamlit_app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Streamlit アプリケーションコードをコピー
COPY ./streamlit_app /app/streamlit_app
# ポートを公開
EXPOSE 8080
# アプリケーションを実行
CMD ["python", "-m", "streamlit", "run", "streamlit_app/main.py", "--server.port=8080", "--server.address=0.0.0.0"]
EOGF

# firestore.rules
cat << 'EOGF' > firestore.rules
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // デフォルトですべてのコレクションへの直接アクセスを拒否
    match /{document=**} {
      allow read, write: if false;
    }
  }
}
EOGF

# firebase.json
cat << 'EOGF' > firebase.json
{
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  }
}
EOGF
touch firestore.indexes.json

# README.md (既に存在する場合は上書きされます)
cat << 'EOGF' > README.md
# Secure Chat Application

Streamlit + Cloud Functions + Firestore + Google Login

## Setup Steps

1.  **Prerequisites:** Ensure `gcloud` CLI, `firebase` CLI, `git`, and `openssl` are installed and configured. Have your GCP Project ID ready.
2.  **Run GCP Setup:** Execute the GCP setup commands (either from the provided script or manually) to create Service Accounts, enable APIs, configure WIF, and set up Secret Manager secrets (entering OAuth credentials when prompted).
3.  **Generate Project Files:** Run `./generate_project_files.sh <YOUR_GCP_PROJECT_ID>` in an empty directory (or after cleaning up).
4.  **Edit Files:** Manually edit the following files with your specific values:
    *   `.github/workflows/deploy.yml`: Update `env` variables (`PROJECT_ID`, `REGION`, `SERVICE_NAME`, etc.) and **critically** the `workload_identity_provider` and `service_account` under the `auth` step. `CHAT_API_FUNCTION_URL` will be updated later.
    *   `streamlit_app/main.py`: Modify the default `ALLOWED_CHAT_PARTNERS` list or plan to set the environment variable.
5.  **Deploy Firestore Rules:** Run `firebase deploy --only firestore:rules` (ensure `firebase login` and `firebase use <YOUR_GCP_PROJECT_ID>` are done).
6.  **Deploy Cloud Function:** Run the `gcloud functions deploy ...` command (provided separately). **Copy the HTTPS Trigger URL.**
7.  **Update Workflow:** Paste the copied Function URL into `.github/workflows/deploy.yml` for the `CHAT_API_FUNCTION_URL` variable.
8.  **Git & Push:** Initialize a Git repository (if needed), add all files, commit, add your GitHub remote, and push.
9.  **Verify Deployment:** Check GitHub Actions for the Cloud Run deployment status. Access the Cloud Run URL to test the application.
10. **Verify Configuration (Optional):** Run `./check_gcp_setup.sh <YOUR_GCP_PROJECT_ID>` to verify resource settings.

## Local Testing

1.  Install dependencies: `pip install -r streamlit_app/requirements.txt`
2.  Edit `streamlit_app/config.yaml`: Uncomment and fill in your OAuth `client_id` and `client_secret` for local testing.
3.  Set environment variable: `export CHAT_API_FUNCTION_URL="<YOUR_DEPLOYED_FUNCTION_URL_OR_LOCAL_EMULATOR_URL>"`
4.  (Optional) Run Firestore emulator: `firebase emulators:start --only firestore`
5.  (Optional) Run Functions emulator locally (using Functions Framework).
6.  Run Streamlit app: `python -m streamlit run streamlit_app/main.py`

## Important Note

This setup relies on `streamlit-authenticator` storing the Google ID token in `st.session_state`. Verify this behavior and adjust `streamlit_app/core/api_client.py` (`get_id_token` function) if necessary.
EOGF

# .github/workflows/deploy.yml (プレースホルダーは手動編集が必要)
cat << 'EOGF' > .github/workflows/deploy.yml
name: Build and Deploy Streamlit App to Cloud Run
on:
  push:
    branches: [ "main" ]
env:
  PROJECT_ID: your-project-id # <<< 要変更: あなたのGCPプロジェクトID
  REGION: asia-northeast1 # <<< 要変更: デプロイするリージョン
  SERVICE_NAME: your-chat-app-name # <<< 要変更: Cloud Run サービス名
  ARTIFACT_REGISTRY: your-artifact-registry-repo # <<< 要変更: Artifact Registry リポジトリ名
  GAR_LOCATION: asia-northeast1 # <<< 要変更: Artifact Registry のリージョン
  APP_SA_EMAIL: your-app-service-account@your-project-id.iam.gserviceaccount.com # <<< 要変更: Cloud Runに割り当てるSA
  FUNC_NAME: chat-api # Cloud Functions の名前 (固定)
  FUNC_SA_EMAIL: your-func-sa@your-project-id.iam.gserviceaccount.com # <<< 要変更: Functions 用 SA
  DEPLOY_SA_EMAIL: your-deploy-sa@your-project-id.iam.gserviceaccount.com # <<< 要変更: デプロイ用SA
  # CHAT_API_FUNCTION_URL: # <<< デプロイ後に動的に設定される
  # ALLOWED_CHAT_PARTNERS: "user1@example.com,user2@example.com" # オプション: 環境変数でチャット相手を指定する場合
jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: 'read'
      id-token: 'write' # Required for Workload Identity Federation
    steps:
    - name: Checkout code
      uses: actions/checkout@v4
    - name: Authenticate to Google Cloud (WIF)
      id: auth
      uses: google-github-actions/auth@v2
      with:
        # !!! 重要: この値はあなたの GCP WIF 設定に合わせて手動で変更してください !!!
        workload_identity_provider: 'projects/YOUR_PROJECT_NUMBER/locations/global/workloadIdentityPools/your-pool-id/providers/your-provider-id'
        service_account: ${{ env.DEPLOY_SA_EMAIL }} # Deploy SA を使用
    - name: Set up Cloud SDK
      uses: google-github-actions/setup-gcloud@v2

    # --- Firestore Rules Deploy ---
    - name: Setup Firebase CLI
      uses: setup-node/setup-node@v3
      with:
        node-version: '18'
    - name: Install Firebase CLI
      run: npm install -g firebase-tools
    - name: Deploy Firestore Rules
      run: firebase deploy --only firestore:rules --project ${{ env.PROJECT_ID }} --token ${{ steps.auth.outputs.access_token }} --non-interactive

    # --- Cloud Functions Deploy ---
    - name: Deploy Cloud Function (${{ env.FUNC_NAME }})
      id: deploy-function
      run: |-
        gcloud functions deploy ${{ env.FUNC_NAME }} \
          --gen2 \
          --runtime python311 \
          --region ${{ env.REGION }} \
          --source ./cloud_functions/chat_api \
          --entry-point app \
          --trigger-http \
          --allow-unauthenticated \
          --service-account ${{ env.FUNC_SA_EMAIL }} \
          --env-vars-file ./cloud_functions/chat_api/.env.yaml \
          --project ${{ env.PROJECT_ID }} \
          --format='value(https_trigger.url)' > function_url.txt

    - name: Get Cloud Function URL
      id: get-function-url
      run: echo "url=$(cat function_url.txt)" >> $GITHUB_OUTPUT

    # --- Docker Build & Push ---
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3
    - name: Configure Docker for Artifact Registry
      run: gcloud auth configure-docker ${{ env.GAR_LOCATION }}-docker.pkg.dev --quiet
    - name: Build and push Docker image
      uses: docker/build-push-action@v5
      with:
        context: .
        push: true
        tags: ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.ARTIFACT_REGISTRY }}/${{ env.SERVICE_NAME }}:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max

    # --- Cloud Run Deploy ---
    - name: Deploy to Cloud Run
      id: deploy-run
      uses: google-github-actions/deploy-cloudrun@v2
      with:
        service: ${{ env.SERVICE_NAME }}
        region: ${{ env.REGION }}
        image: ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.ARTIFACT_REGISTRY }}/${{ env.SERVICE_NAME }}:${{ github.sha }}
        service_account: ${{ env.APP_SA_EMAIL }}
        secrets: |-
          GOOGLE_CLIENT_ID=google-client-id:latest
          GOOGLE_CLIENT_SECRET=google-client-secret:latest
          COOKIE_KEY=cookie-key:latest
          COOKIE_NAME=cookie-name:latest
        env_vars: |-
          CHAT_API_FUNCTION_URL=${{ steps.get-function-url.outputs.url }}
          # ALLOWED_CHAT_PARTNERS=${{ env.ALLOWED_CHAT_PARTNERS }} # 必要ならコメント解除

    - name: Show Cloud Run Service URL
      run: echo "Cloud Run Service URL: ${{ steps.deploy-run.outputs.url }}"
EOGF

# cloud_functions/chat_api/requirements.txt
cat << 'EOGF' > cloud_functions/chat_api/requirements.txt
Flask>=2.0.0
google-cloud-firestore>=2.14.0
google-auth>=2.15.0
pytz>=2023.3
gunicorn
EOGF

# cloud_functions/chat_api/.env.yaml (PROJECT_NUMBER を変数で埋め込み)
cat << EOF > cloud_functions/chat_api/.env.yaml
# Secret Manager から OAuth クライアント ID (Streamlitアプリ用) を読み込む
GOOGLE_OAUTH_CLIENT_ID: projects/${PROJECT_NUMBER}/secrets/google-client-id/versions/latest
