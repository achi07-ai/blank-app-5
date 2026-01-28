import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="Task Calendar", layout="wide")
st.title("📅 カテゴリ別カレンダー & 自動リマインダー")

# --- リマインダー計算ロジック ---
def calculate_reminder(event_date, category):
    if category == "テスト":
        return event_date - timedelta(weeks=2)
    elif category == "課題":
        return event_date - timedelta(days=3)
    elif category == "日用品":
        return event_date + relativedelta(months=1)
    elif category == "遊び":
        return event_date - timedelta(days=1)
    else: # その他
        return None

# --- 1. 新しい予定の追加 (サイドバー) ---
with st.sidebar:
    st.header("新しく予定を追加")
    with st.form("add_event_form", clear_on_submit=True):
        title = st.text_input("予定名")
        event_date = st.date_input("予定日", datetime.now())
        category = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "その他"])
        submitted = st.form_submit_button("保存")

        if submitted and title:
            # リマインダー日の計算
            reminder_date = calculate_reminder(event_date, category)
            reminder_str = reminder_date.strftime('%Y-%m-%d') if reminder_date else None
            
            # Supabaseへの保存
            data = {
                "title": title,
                "start": event_date.strftime('%Y-%m-%d'),
                "category": category,
                "reminder_at": reminder_str
            }
            supabase.table("todos").insert(data).execute()
            st.success(f"追加完了: {category}のリマインダーを設定しました")
            st.rerun()

# --- 2. データの取得と整形 ---
response = supabase.table("todos").select("*").execute()
events = []
for item in response.data:
    # カレンダー表示用の色分け
    colors = {
        "テスト": "#FF4B4B", "課題": "#FFA421", 
        "日用品": "#7792E3", "遊び": "#21C354", "その他": "#A3A8B4"
    }
    events.append({
        "title": f"[{item['category']}] {item['title']}",
        "start": item['start'],
        "backgroundColor": colors.get(item['category'], "#3D3333")
    })

# --- 3. カレンダーの表示 ---
calendar_options = {
    "editable": "true",
    "selectable": "true",
    "headerToolbar": {
        "left": "today prev,next",
        "center": "title",
        "right": "dayGridMonth,dayGridWeek,dayGridDay",
    },
    "initialView": "dayGridMonth",
}

state = calendar(events=events, options=calendar_options)

# --- 4. リマインダー確認エリア ---
st.divider()
st.subheader("🔔 近日のリマインダー設定一覧")
reminders = supabase.table("todos").select("*").not_.is_("reminder_at", "null").order("reminder_at").execute()

if reminders.data:
    for r in reminders.data:
        st.write(f"⏰ **{r['reminder_at']}**： {r['category']} 「{r['title']}」のリマインダー")
