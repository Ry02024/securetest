# (内容は変更なし)
import streamlit as st

st.set_page_config(page_title="About", page_icon="ℹ️")

st.markdown("# About このアプリについて")
st.sidebar.header("About")
st.write(
    """
    このアプリケーションは、Streamlit、Cloud Functions、Firestore を使用した
    セキュアなチャットアプリケーションのデモです。

    **主な機能:**
    - Google アカウントによる認証
    - 選択した相手とのリアルタイムチャット
    - Cloud Functions 経由での安全な Firestore アクセス
    """
)

# ログイン状態に応じて追加情報を表示
if st.session_state.get("authentication_status"):
    st.write("ログイン中です。")
    st.write(f"ユーザー名: {st.session_state.get('name')}")
    st.write(f"メールアドレス: {st.session_state.get('email')}")
else:
    st.warning("ログインしていません。メインページからログインしてください。")

