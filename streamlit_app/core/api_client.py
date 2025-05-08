# (内容は変更なし)
import os
import datetime
import pytz
import requests # requests をインポート
import streamlit as st # st.session_state を使うため
import json # JSON パース用

# --- 定数 ---
# デプロイした Cloud Functions の URL を環境変数から取得
FUNCTION_URL = os.environ.get("CHAT_API_FUNCTION_URL")
if not FUNCTION_URL:
    # 環境変数が設定されていない場合は警告を表示 (ローカル実行時など)
    st.warning("環境変数 CHAT_API_FUNCTION_URL が設定されていません。API呼び出しは失敗します。")
    # ローカルテスト用にデフォルト値を設定する場合 (非推奨)
    # FUNCTION_URL = "http://localhost:8081" # ローカル Functions Emulator の URL

jst = pytz.timezone('Asia/Tokyo')

# --- ヘルパー関数 ---
def get_id_token():
    """
    Streamlit セッションステートから ID トークンを取得します。
    streamlit-authenticator が Google ログイン後に ID トークンを
    セッションに保存するキーを確認し、必要であればキー名を修正してください。
    一般的なキー名は 'id_token' や credentials の中などですが、ライブラリの実装によります。
    """
    # まず 'credentials' 内の 'id_token' を試す (streamlit-authenticator の構造例)
    id_token_val = st.session_state.get("credentials", {}).get("id_token")

    if not id_token_val:
        # 次にセッションステート直下の 'id_token' を試す (別の可能性)
        id_token_val = st.session_state.get("id_token")

    if not id_token_val:
         st.error("認証に必要なIDトークンが見つかりません。再度ログインしてください。")
         print("Error: ID Token not found in st.session_state. Checked keys: ['credentials']['id_token'], ['id_token']")
         return None # トークンが見つからない場合は None を返す

    # print(f"Debug: Found ID Token (first 10 chars): {id_token_val[:10]}...") # デバッグ用
    return id_token_val

def call_function(action, payload):
    """Cloud Functions を呼び出す共通関数"""
    if not FUNCTION_URL:
        st.error("Cloud Functions の URL が設定されていません。")
        return None

    id_token = get_id_token()
    if not id_token:
        # get_id_token 内でエラー表示されるので、ここでは None を返すだけ
        return None

    headers = {
        'Authorization': f'Bearer {id_token}',
        'Content-Type': 'application/json'
    }
    data = {'action': action, **payload}

    print(f"Calling Cloud Function: {FUNCTION_URL} Action: {action}") # デバッグログ
    try:
        response = requests.post(FUNCTION_URL, headers=headers, json=data, timeout=30) # タイムアウト設定
        response.raise_for_status() # HTTPエラー (4xx, 5xx) があれば例外を発生させる

        print(f"Cloud Function Response Status: {response.status_code}") # デバッグログ
        # レスポンスボディが空の場合もあるのでチェック
        if response.content:
            return response.json()
        else:
            # ボディが空でも成功 (2xx) の場合がある (例: send_message の 200 OK)
            return {"success": True, "message": "Action completed successfully (no content)"}

    except requests.exceptions.Timeout:
         st.error(f"Cloud Functions の呼び出しがタイムアウトしました。({FUNCTION_URL})")
         print(f"Error: Cloud Function call timed out for action {action}")
         return None
    except requests.exceptions.ConnectionError:
         st.error(f"Cloud Functions に接続できませんでした。({FUNCTION_URL})")
         print(f"Error: Could not connect to Cloud Function for action {action}")
         return None
    except requests.exceptions.HTTPError as e:
        st.error(f"Cloud Functions 呼び出しエラー (HTTP {e.response.status_code})")
        try:
            error_detail = e.response.json()
            st.error(f"エラー詳細: {error_detail.get('error', e.response.text)}")
            print(f"Error: Cloud Function HTTP Error {e.response.status_code} for action {action}. Detail: {error_detail}")
        except json.JSONDecodeError:
            st.error(f"エラーレスポンス: {e.response.text}")
            print(f"Error: Cloud Function HTTP Error {e.response.status_code} for action {action}. Response: {e.response.text}")
        return None
    except json.JSONDecodeError:
        st.error("Cloud Functions からの応答が不正な形式 (JSONではない) でした。")
        print(f"Error: Invalid JSON response from Cloud Function for action {action}")
        return None
    except Exception as e:
        st.error(f"Cloud Functions 呼び出し中に予期せぬエラーが発生しました: {e}")
        print(f"Error: Unexpected error during Cloud Function call for action {action}: {e}")
        return None

# --- API 操作関数 (Functions 経由) ---
def get_messages(room_id):
    """Cloud Functions 経由でメッセージを取得"""
    if not room_id:
        st.warning("チャットルームIDが指定されていません。")
        return []
    response = call_function('get_messages', {'room_id': room_id})
    if response and 'messages' in response and isinstance(response['messages'], list):
        messages_data = []
        for msg in response['messages']:
            if isinstance(msg, dict) and 'timestamp' in msg and isinstance(msg['timestamp'], str):
                try:
                    # ISOフォーマット文字列から timezone-aware な datetime オブジェクトに変換
                    utc_time = datetime.datetime.fromisoformat(msg['timestamp'])
                    # Functions は UTC で返すはずだが、念のため timezone 確認
                    if utc_time.tzinfo is None:
                        utc_time = pytz.utc.localize(utc_time)
                    # JST に変換して格納
                    msg['timestamp_jst'] = utc_time.astimezone(jst)
                except (ValueError, TypeError) as e:
                    print(f"Timestamp parsing/conversion error: {e} for value {msg['timestamp']}")
                    msg['timestamp_jst'] = None # パース/変換失敗
            else:
                 msg['timestamp_jst'] = None # タイムスタンプがないか形式が違う場合

            messages_data.append(msg)
        return messages_data
    elif response and response.get('error'):
        # call_function でエラー表示されるのでここではログのみ
        print(f"Error received from get_messages API: {response.get('error')}")
    return [] # エラーまたはメッセージがない場合

def send_message(room_id, receiver_email, content):
    """Cloud Functions 経由でメッセージを送信"""
    if not all([room_id, receiver_email, content]):
         st.error("メッセージの送信に必要な情報が不足しています。")
         return False

    payload = {
        'room_id': room_id,
        'receiver_email': receiver_email,
        'content': content
        # sender_email は Functions が ID トークンから取得・検証する
    }
    response = call_function('send_message', payload)
    # 成功レスポンスは {'success': True} またはボディなしの 200 OK を期待
    success = response is not None and response.get('success', False)
    if not success:
        print(f"Failed to send message via API. Response: {response}")
    return success

# (オプション) 認証済みユーザーリスト取得APIを実装した場合
# def get_available_users():
#     """Cloud Functions 経由で利用可能なユーザーリストを取得"""
#     response = call_function('get_users', {})
#     if response and 'users' in response and isinstance(response['users'], list):
#         return response['users']
#     return [] # エラー時やユーザーがいない場合は空リスト

# --- タイムスタンプ表示用ヘルパー ---
def format_timestamp_for_display(timestamp_obj):
    """datetime オブジェクト (JST想定) を表示用の文字列に変換"""
    if timestamp_obj and isinstance(timestamp_obj, datetime.datetime):
        return timestamp_obj.strftime('%m/%d %H:%M:%S')
    else:
        return "時刻不明" # または他のデフォルト文字列
