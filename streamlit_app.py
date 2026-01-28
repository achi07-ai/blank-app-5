import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta, time
import pytz  # ここで日本時間を扱います

# --- 1. 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="Task Calendar JST", layout="wide")

# 日本標準時 (JST) を定義
JST = pytz.timezone('Asia/Tokyo')

# --- 2. ログイン機能 ---
if "user" not in st.session_state:
    st.title("🔐 ログイン")
    email = st.text_input("メールアドレス")
    password = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception as e: st.error(f"ログイン失敗: {e}")
    st.stop()

user_id = st.session_state.user.id

# --- 3. データ取得 ---
def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

current_todos = get_my_todos()

# --- 4. サイドバー：予定追加 ---
with st.sidebar:
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト"):
        del st.session_state.user
        st.rerun()
    
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        title = st.text_input("予定名")
        event_date = st.date_input("日付", datetime.now(JST))
        t_col1, t_col2 = st.columns(2)
        start_t = t_col1.time_input("開始", value=time(10, 0))
        end_t = t_col2.time_input("終了", value=time(11, 0))
        cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
        
        if st.form_submit_button("保存"):
            # 【重要】JST（日本時間）として日時を生成
            start_dt = JST.localize(datetime.combine(event_date, start_t))
            end_dt = JST.localize(datetime.combine(event_date, end_t))
            
            supabase.table("todos").insert({
                "user_id": user_id, "title": title, "category": cat,
                "start_at": start_dt.isoformat(), 
                "end_at": end_dt.isoformat(),
                "is_complete": False
            }).execute()
            st.rerun()

# --- 5. カレンダー表示 ---
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in current_todos:
    prefix = "✅ " if item.get('is_complete') else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": item['start_at'],
        "end": item.get('end_at'),
        "backgroundColor": "#D3D3D3" if item.get('is_complete') else colors.get(item['category'], "#3D3333"),
    })

cal_options = {
    "timeZone": "Asia/Tokyo", # カレンダー表示を日本時間に固定
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "displayEventTime": True,
    "displayEventEnd": True,
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False}
}
calendar(events=events, options=cal_options)
