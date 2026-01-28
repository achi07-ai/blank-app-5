import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="My Private Calendar", layout="wide")

# --- 簡易ログイン機能 ---
if "user" not in st.session_state:
    st.title("🔐 ログイン")
    email = st.text_input("メールアドレス")
    password = st.text_input("パスワード", type="password")
    col1, col2 = st.columns(2)
    
    if col1.button("ログイン"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except:
            st.error("ログインに失敗しました")
            
    if col2.button("新規登録"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("確認メールを送信しました（設定によります）")
        except:
            st.error("登録に失敗しました")
    st.stop()

# --- ログイン後のメイン画面 ---
user_id = st.session_state.user.id
st.sidebar.write(f"👤 {st.session_state.user.email}")
if st.sidebar.button("ログアウト"):
    del st.session_state.user
    st.rerun()

st.title("📅 カテゴリ別マイカレンダー")

# リマインダー計算ロジック
def calculate_reminder(event_date, category):
    rules = {"テスト": timedelta(weeks=-2), "課題": timedelta(days=-3), "遊び": timedelta(days=-1)}
    if category == "日用品": return event_date + relativedelta(months=1)
    return event_date + rules.get(category, timedelta(0)) if category in rules else None

# --- 1. 予定の追加・編集フォーム ---
with st.sidebar:
    st.header("予定の操作")
    mode = st.radio("モード選択", ["新規追加", "編集・削除"])
    
    # ユーザー自身のデータのみ取得
    response = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    todos_df = response.data

    if mode == "新規追加":
        with st.form("add_form"):
            title = st.text_input("予定名")
            event_date = st.date_input("予定日")
            cat = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "その他"])
            if st.form_submit_button("保存"):
                rem = calculate_reminder(event_date, cat)
                supabase.table("todos").insert({
                    "title": title, "start": str(event_date), "category": cat, 
                    "reminder_at": str(rem) if rem else None, "user_id": user_id
                }).execute()
                st.rerun()
    
    elif mode == "編集・削除" and todos_df:
        target = st.selectbox("対象を選択", todos_df, format_func=lambda x: x['title'])
        with st.form("edit_form"):
            new_title = st.text_input("予定名", value=target['title'])
            new_done = st.checkbox("完了済み", value=target.get('is_complete', False))
            if st.form_submit_button("更新"):
                supabase.table("todos").update({"title": new_title, "is_complete": new_done}).eq("id", target['id']).execute()
                st.rerun()
        if st.button("🗑️ この予定を削除"):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()

# --- 2. カレンダー表示 ---
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "その他": "#A3A8B4"}

for item in todos_df:
    title_prefix = "✅ " if item.get('is_complete') else ""
    events.append({
        "title": f"{title_prefix}[{item['category']}] {item['title']}",
        "start": item['start'],
        "backgroundColor": "#D3D3D3" if item.get('is_complete') else colors.get(item['category'], "#3D3333"),
        "id": str(item['id'])
    })

calendar(events=events, options={"initialView": "dayGridMonth"})

# --- 3. リマインダー一覧 ---
st.subheader("🔔 あなたのリマインダー")
reminders = [r for r in todos_df if r['reminder_at'] and not r.get('is_complete')]
for r in sorted(reminders, key=lambda x: x['reminder_at']):
    st.write(f"⏰ {r['reminder_at']} : {r['title']}")
