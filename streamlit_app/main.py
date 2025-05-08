# (内容は変更なし)
import streamlit as st
import yaml
from streamlit_authenticator import Authenticate
from streamlit_authenticator.utilities.exceptions import LoginError #, RegisterError, ForgotError # 必要に応じて
import os
import sys
from pathlib import Path
import datetime

# --- モジュールインポートと API クライアント初期化 ---
# 新しいディレクトリ構造に合わせて core.api_client をインポート
try:
    # 同じ streamlit_app パッケージ内の core モジュールからインポート
    from core.api_client import get_messages, send_message, format_timestamp_for_display
    # (もしユーザーリスト取得APIを実装したら) from core.api_client import get_available_users
except ImportError:
    # ローカル実行時 (python -m streamlit run streamlit_app/main.py) のためのパス解決
    # プロジェクトルートをパスに追加
    project_root = str(Path(__file__).resolve().parent.parent)
    if project_root not in sys.path:
        sys.path.append(project_root)
    try:
        from streamlit_app.core.api_client import get_messages, send_message, format_timestamp_for_display
        # from streamlit_app.core.api_client import get_available_users
    except ImportError as e:
         st.error(f"モジュールのインポートに失敗しました: {e}. パスを確認してください。")
         st.stop()


# --- 認証設定の読み込み ---
config = None
try:
    # 優先度: 環境変数 (Cloud Runデプロイ時) > config.yaml (ローカルテスト時)
    # 環境変数から読み込むキー名は GitHub Actions や Cloud Run 設定と合わせる
    if os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET') and os.getenv('COOKIE_KEY') and os.getenv('COOKIE_NAME'):
        print("Loading auth config from environment variables.")
        config = {
            'credentials': {
                'google_oauth': {
                    'client_id': os.getenv('GOOGLE_CLIENT_ID'),
                    'client_secret': os.getenv('GOOGLE_CLIENT_SECRET')
                }
            },
            'cookie': {
                'expiry_days': int(os.getenv('COOKIE_EXPIRY_DAYS', 30)), # 環境変数なければデフォルト30日
                'key': os.getenv('COOKIE_KEY'),
                'name': os.getenv('COOKIE_NAME')
            },
            'preauthorized': {
                'emails': os.getenv('PREAUTHORIZED_EMAILS', '').split(',') if os.getenv('PREAUTHORIZED_EMAILS') else []
            }
        }
    elif os.path.exists('streamlit_app/config.yaml'):
        print("Loading auth config from streamlit_app/config.yaml.")
        # config.yaml のパスを修正
        with open('streamlit_app/config.yaml') as file:
            config_from_file = yaml.safe_load(file)
            # ローカルテスト用に OAuth 情報が設定されているか確認
            if (not config_from_file.get('credentials', {}).get('google_oauth', {}).get('client_id') or
                not config_from_file.get('credentials', {}).get('google_oauth', {}).get('client_secret')):
                 st.warning("ローカルテスト用の OAuth クライアント情報が config.yaml に設定されていません。Google ログインは機能しません。")
            config = config_from_file
    else:
         st.error("🚨 認証設定ファイル (streamlit_app/config.yaml) または関連する環境変数が見つかりません。")
         st.stop()

    # 設定が最低限読み込めたか確認
    if not config or 'credentials' not in config or 'cookie' not in config:
         st.error("🚨 認証設定の読み込みに失敗したか、形式が正しくありません。")
         st.stop()

except FileNotFoundError:
     st.error("🚨 streamlit_app/config.yaml が見つかりません。")
     st.stop()
except yaml.YAMLError as e:
     st.error(f"🚨 config.yaml の解析中にエラーが発生しました: {e}")
     st.stop()
except Exception as e:
    st.error(f"🚨 認証設定の読み込み中に予期せぬエラーが発生しました: {e}")
    st.exception(e) # 詳細なトレースバックを表示
    st.stop()


# --- 認証オブジェクトの初期化とログイン処理 ---
# streamlit-authenticator の Authenticate インスタンスを作成
try:
    authenticator = Authenticate(
        config['credentials'],
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days'],
        config['preauthorized']['emails']
    )
except Exception as e:
    st.error(f"🚨 Authenticator の初期化に失敗しました: {e}")
    st.exception(e)
    st.stop()

# --- Google ログインボタン (ダミー) ---
# ログイン状態はセッションステートで管理する想定
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

# ユーザーがログインしていない場合にボタンを表示
if st.session_state.user_info is None:
    st.write("Google アカウントでログインしてください。") # 案内メッセージ
    if st.button("️ G Google でログイン", key="google_login_placeholder"):
        # --- ここに実際の Google ログイン処理を後で追加 ---
        st.info("（Google ログイン処理を実行します... 未実装）")
        # 現時点ではボタンを押しても何も起こらない（表示だけ）
        # 実際の処理では、Googleの認証エンドポイントにリダイレクトするなどの動作が必要
else:
    # --- ログイン後の処理 ---
    # (ここに、ログイン後に表示したい内容、例えばチャットUIなどを記述)
    st.success(f"ようこそ、{st.session_state.user_info.get('name', 'ユーザー')}さん！") # 仮の表示
    if st.button("ログアウト (仮)", key="logout_placeholder"):
        st.session_state.user_info = None
        st.rerun() # ログアウトしたら画面を再読み込み
        
# Google ログインボタンを表示
# 'main' はログインフォームが表示される場所の識別子
# 'fields' でフォーム名をカスタマイズ
try:
    authenticator.login(location='main', fields={'Form name': 'Google アカウントでログイン'})
except LoginError as e:
    st.error(f"ログインエラーが発生しました: {e}")
    st.stop()
except Exception as e:
    # ネットワークエラーなどで Google 認証自体に失敗した場合など
    st.error(f"🚨 ログイン処理中に予期せぬエラーが発生しました: {e}")
    st.exception(e)
    st.stop()

# --- 認証後のアプリケーション表示 ---
# st.session_state["authentication_status"] は True, False, None のいずれか
if st.session_state.get("authentication_status"):
    sender_email = st.session_state.get("email")
    sender_name = st.session_state.get("name")

    # --- サイドバー: ログイン情報とチャット相手選択 ---
    st.sidebar.success(f"ログイン中: **{sender_name}**")
    st.sidebar.caption(f"({sender_email})")
    # サイドバーにログアウトボタンを配置
    authenticator.logout('ログアウト', 'sidebar')

    st.sidebar.markdown("---")
    st.sidebar.subheader("チャット相手")

    # --- チャット相手の選択 ---
    try:
        # ここではデモ用に環境変数から取得する例
        # 将来的には get_available_users() API を使うことを検討
        allowed_partners_str = os.getenv("ALLOWED_CHAT_PARTNERS", "") # 環境変数からカンマ区切りで取得
        if allowed_partners_str:
            all_users = [email.strip() for email in allowed_partners_str.split(',')]
        else:
            # 環境変数がなければ、固定リスト（デモ用）
             all_users = ["user1@example.com", "user2@example.com"] # <<< 要変更: 実際のユーザーリスト
             st.sidebar.warning("デモ用ユーザーリストを使用中。環境変数 ALLOWED_CHAT_PARTNERS を設定してください。")

        # 自分以外のユーザーをチャット相手候補とする
        available_partners = [user for user in all_users if user.lower() != sender_email.lower()]

        if not available_partners:
            st.sidebar.warning("チャット可能な相手がいません。")
            st.info("現在チャットできる相手がいません。")
            st.stop()

        # ドロップダウンでチャット相手を選択
        receiver_email = st.sidebar.selectbox(
            "相手を選択:",
            available_partners,
            key="receiver_select",
            index=None, # 初期選択なし
            placeholder="選択してください..."
        )

    except Exception as e:
        st.sidebar.error("ユーザーリストの処理中にエラーが発生しました。")
        st.error(f"🚨 ユーザーリストエラー: {e}")
        st.stop()

    # --- メイン画面: チャット表示と入力 ---
    if receiver_email:
        st.title("🔒 セキュアチャット")
        st.info(f"💬 **{receiver_email}** とチャット中")

        # チャットルームIDを決定 (メールアドレスを小文字にし、アルファベット順で結合)
        room_id = "_".join(sorted([sender_email.lower(), receiver_email.lower()]))
        st.caption(f"Room ID (internal): `{room_id}`") # デバッグ用に表示

        # --- メッセージ表示エリア ---
        st.markdown("---")
        st.subheader("メッセージ履歴")
        # メッセージ表示用に高さ固定のコンテナを作成 (スクロール可能にする)
        message_area = st.container()
        # message_area.height = 400 # 高さを固定したい場合

        try:
            # API クライアント経由でメッセージを取得
            messages = get_messages(room_id)

            with message_area:
                if not messages:
                    st.info("まだメッセージはありません。最初のメッセージを送信しましょう！")
                else:
                    # メッセージをループして表示
                    for msg in messages:
                        msg_sender = msg.get('sender_email', '不明な送信者')
                        msg_content = msg.get('content', '')
                        # タイムスタンプは api_client で JST datetime オブジェクトに変換済み想定
                        timestamp_str = format_timestamp_for_display(msg.get('timestamp_jst'))

                        # 自分が送信したメッセージかどうかを判定
                        is_sender = (msg_sender.lower() == sender_email.lower())

                        # st.chat_message を使ってチャット風に表示
                        # name は表示名、avatar はアイコン (文字列 or URL)
                        avatar_icon = "🧑‍💻" if is_sender else "🤖" # またはユーザーアイコンURLなど
                        with st.chat_message(name="user" if is_sender else "assistant", avatar=avatar_icon):
                             # メタ情報（送信者名と時刻）を表示
                             st.caption(f"{'あなた' if is_sender else msg_sender.split('@')[0]} ({timestamp_str})")
                             # メッセージ内容を表示
                             st.write(msg_content)

        except Exception as e:
            st.error(f"🚨 メッセージの読み込み中にエラーが発生しました: {e}")
            st.exception(e)

        # --- メッセージ入力フォーム ---
        st.markdown("---") # 区切り線

        # シンプルな Text Input + Button
        message_content = st.text_input("メッセージを入力:", key=f"msg_input_{room_id}", label_visibility="collapsed", placeholder="ここにメッセージを入力...")
        if st.button("送信", key=f"send_btn_{room_id}"):
            if message_content:
                 try:
                     # API クライアント経由でメッセージを送信
                     success = send_message(room_id, receiver_email, message_content)
                     if success:
                         # 送信成功したら入力欄をクリアし、メッセージリストを再読み込みするために rerun
                         st.rerun()
                     else:
                         st.error("メッセージの送信に失敗しました。")
                 except Exception as e:
                     st.error(f"🚨 送信処理中にエラーが発生しました: {e}")
                     st.exception(e)
            else:
                 st.warning("メッセージを入力してください。")

    else:
        # チャット相手が選択されていない場合
        st.info("⬅️ サイドバーからチャット相手を選択してください。")

# --- ログイン前 / 失敗時の表示 ---
elif st.session_state.get("authentication_status") is False:
    st.error('メールアドレスまたはパスワードが間違っているか、Google 認証に失敗しました。')
    # ログイン失敗時の詳細なエラーは LoginError 例外で捕捉されるべき
elif st.session_state.get("authentication_status") is None:
    st.warning('トップのボタンから Google アカウントでログインしてください。')

# --- デバッグ情報表示 (必要に応じてコメント解除) ---
# st.sidebar.markdown("---")
# st.sidebar.subheader("Debug Info")
# st.sidebar.json(st.session_state) # セッションステートの内容を JSON で表示
