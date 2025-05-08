# (内容は変更なし)
import os
import datetime
import pytz
from flask import Flask, request, jsonify
from google.cloud import firestore
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import traceback # エラー詳細表示用

# --- 定数 ---
# 環境変数から OAuth クライアント ID を取得 (デプロイ時に .env.yaml から設定される)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
if not GOOGLE_CLIENT_ID:
    print("警告: 環境変数 GOOGLE_OAUTH_CLIENT_ID が設定されていません。IDトークン検証に失敗する可能性があります。")
    # ローカルテスト用にデフォルト値を設定する場合（推奨しません）
    # if os.environ.get('FUNCTIONS_EMULATOR'): GOOGLE_CLIENT_ID = "YOUR_LOCAL_TEST_CLIENT_ID"

# Firestore クライアント初期化 (Functions の実行環境のSAを使用)
db = firestore.Client()
jst = pytz.timezone('Asia/Tokyo')

# Flask アプリケーションの作成
app = Flask(__name__)

# --- 認証ヘルパー関数 ---
def verify_id_token(auth_header):
    """Authorization ヘッダーから ID トークンを検証し、ユーザー情報を返す"""
    if not auth_header or not auth_header.startswith('Bearer '):
        raise ValueError("Invalid Authorization header: Missing or invalid format.")

    token = auth_header.split('Bearer ')[1]
    if not token:
        raise ValueError("Invalid Authorization header: Token is empty.")

    if not GOOGLE_CLIENT_ID:
         raise ConnectionError("Server configuration error: Google Client ID is not set.")

    try:
        # ID トークンを検証
        # audience には、この Functions を呼び出すクライアント (Streamlit アプリ) の OAuth クライアントID を指定
        # これにより、意図しないクライアントからの呼び出しを防ぐ
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID # 環境変数から取得したクライアントID
        )
        # ここで特定の issuer や hosted domain (hd) のチェックを追加することも可能
        # 例: if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
        #       raise ValueError('Wrong issuer.')
        # 例: if 'hd' not in idinfo or idinfo['hd'] != 'your-domain.com':
        #       raise ValueError('Unauthorized domain.')

        print(f"ID token successfully verified for user: {idinfo.get('email')}")
        return idinfo # 検証済みのユーザー情報 (email, name, sub などを含む辞書)

    except ValueError as e:
        # トークンが無効または検証に失敗した場合 (audience 不一致など)
        print(f"ID token verification failed: {e}")
        raise ValueError(f"Invalid or expired ID token: {e}") # 401 Unauthorized が適切か
    except Exception as e:
        print(f"An unexpected error occurred during token verification: {e}")
        raise ConnectionError(f"Token verification internal error: {e}") # 500 Internal Server Error が適切か


# --- Firestore 操作関数 ---
def get_messages_from_db(room_id, limit=50):
    """Firestore からメッセージを取得"""
    messages = []
    messages_ref = db.collection("chat_rooms").document(room_id).collection("messages")
    messages_stream = messages_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit).stream()
    for msg_doc in messages_stream:
        msg_data = msg_doc.to_dict()
        # Firestore の Timestamp を ISO 形式文字列に変換して JSON で返しやすくする
        if 'timestamp' in msg_data and isinstance(msg_data['timestamp'], datetime.datetime):
             # Firestore から取得したタイムスタンプは UTC であると想定
             # naive な場合、UTC を付与
             if msg_data['timestamp'].tzinfo is None:
                 msg_data['timestamp'] = pytz.utc.localize(msg_data['timestamp'])
             # ISO形式に変換
             msg_data['timestamp'] = msg_data['timestamp'].isoformat()
        messages.append(msg_data)
    messages.reverse() # 古い順に戻す
    return messages

def send_message_to_db(room_id, sender_email, receiver_email, content):
    """Firestore にメッセージを保存"""
    if not all([room_id, sender_email, receiver_email, content]):
        raise ValueError("Missing required message data.")
    messages_ref = db.collection("chat_rooms").document(room_id).collection("messages")
    new_msg_ref = messages_ref.document()
    # 保存するデータ。sender_email は検証済みトークンの email を使う
    data_to_send = {
        'sender_email': sender_email, # トークンから取得したメールアドレス
        'receiver_email': receiver_email, # リクエストから取得
        'content': content, # リクエストから取得
        'timestamp': datetime.datetime.now(pytz.utc) # UTCで保存
    }
    new_msg_ref.set(data_to_send)
    print(f"Message saved to room {room_id} by {sender_email}")
    return True

# --- HTTP リクエストハンドラ ---
@app.route('/', methods=['POST'])
def handle_request():
    """HTTP POST リクエストを処理するメイン関数"""
    try:
        # 1. 認証: ID トークンを検証
        auth_header = request.headers.get('Authorization')
        user_info = verify_id_token(auth_header)
        user_email = user_info.get('email')
        if not user_email:
            # 通常 verify_id_token が成功すれば email は存在するはずだが念のため
            return jsonify({"error": "Email not found in verified token"}), 403

        # 2. リクエストボディを取得
        req_data = request.get_json()
        if not req_data:
            return jsonify({"error": "Invalid request: Missing JSON body"}), 400
        if 'action' not in req_data:
            return jsonify({"error": "Invalid request: Missing 'action' in JSON body"}), 400

        action = req_data.get('action')

        # 3. アクションに応じた処理を実行
        if action == 'get_messages':
            room_id = req_data.get('room_id')
            if not room_id:
                return jsonify({"error": "Missing 'room_id' parameter"}), 400

            # Firestore からメッセージ取得 (セキュリティチェックはここでも追加可能)
            # 例: room_id に user_email が含まれているかチェックするなど
            if user_email.lower() not in room_id.lower().split('_'):
                 return jsonify({"error": "Forbidden: You are not part of this chat room"}), 403

            messages = get_messages_from_db(room_id)
            return jsonify({"messages": messages}), 200

        elif action == 'send_message':
            room_id = req_data.get('room_id')
            receiver_email = req_data.get('receiver_email')
            content = req_data.get('content')
            if not all([room_id, receiver_email, content]):
                return jsonify({"error": "Missing 'room_id', 'receiver_email', or 'content'"}), 400

            # 送信者は認証されたユーザー自身 (user_email)
            sender_email = user_email

            # セキュリティチェック: room_id と sender/receiver が一致するかなど
            expected_room_id = "_".join(sorted([sender_email.lower(), receiver_email.lower()]))
            if room_id != expected_room_id:
                 return jsonify({"error": "Forbidden: Invalid room_id for sender/receiver pair"}), 403

            send_message_to_db(room_id, sender_email, receiver_email, content)
            return jsonify({"success": True}), 200

        # (オプション) ユーザーリスト取得などのアクションを追加する場合
        # elif action == 'get_users':
        #     # Firestore の users コレクションなどからリストを取得
        #     users = ["user1@example.com", "user2@example.com"] # ダミー
        #     return jsonify({"users": users}), 200

        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

    except ValueError as e: # 認証エラー(401/403)やパラメータ不足(400)
        error_message = str(e)
        status_code = 400
        if "token" in error_message.lower() or "authorization" in error_message.lower():
            status_code = 401 # Unauthorized
        elif "forbidden" in error_message.lower():
            status_code = 403 # Forbidden
        print(f"Client Error ({status_code}): {error_message}")
        return jsonify({"error": error_message}), status_code
    except ConnectionError as e: # サーバー内部の接続や設定エラー
        print(f"Server Configuration/Connection Error: {e}")
        return jsonify({"error": f"Server configuration error: {e}"}), 500
    except Exception as e: # その他の予期せぬエラー
        print(f"An internal server error occurred: {traceback.format_exc()}")
        return jsonify({"error": "An internal server error occurred."}), 500

# Cloud Functions (2nd gen) は Gunicorn などの WSGI サーバーで実行されるため、
# 以下の if __name__ == '__main__': ブロックは通常不要。
# ローカルで Flask 開発サーバーを起動したい場合はコメント解除して使う。
# if __name__ == '__main__':
#     # ローカル実行時はポート8081などで起動 (Streamlitと分ける)
#     port = int(os.environ.get('PORT', 8081))
#     app.run(debug=True, host='0.0.0.0', port=port)
