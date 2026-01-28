import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="Advanced Calendar", layout="wide")

# --- ログイン機能 ---
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
        except: st.error("ログインに失敗しました")
    if col2.button("新規登録"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("登録しました。そのままログインしてください。")
        except: st.error("登録に失敗しました")
    st.stop()

user_id = st.session_state.user.id

# --- リマインダー計算ロジック ---
def calculate_reminder(event_datetime, category):
    rules = {"テスト": timedelta(weeks=-2), "課題": timedelta(days=-3), "遊び": timedelta(days=-1), "バイト": timedelta(days=-1)}
    if category == "日用品": return event_datetime + relativedelta(months=1)
    return event_datetime + rules.get(category, timedelta(0))

# --- データの取得関数 ---
def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

# --- サイドバー操作 ---
with st.sidebar:
    st.title(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト"):
        del st.session_state.user
        st.rerun()
    
    st.divider()
    mode = st.radio("操作", ["追加", "編集・削除"])
    current_todos = get_my_todos()

    if mode == "追加":
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            d_col, t_col = st.columns(2)
            event_date = d_col.date_input("日付")
            event_time = t_col.time_input("時間", value=datetime.strptime("10:00", "%H:%M").time())
            cat = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            if st.form_submit_button("保存"):
                if title:
                    dt = datetime.combine(event_date, event_time)
                    rem = calculate_reminder(dt, cat)
                    # 保存処理
                    supabase.table("todos").insert({
                        "user_id": user_id,
                        "title": title,
                        "category": cat,
                        "start_at": dt.isoformat(),
                        "reminder_at": rem.strftime('%Y-%m-%d') if rem else None
                    }).execute()
                    st.rerun()

    elif mode == "編集・削除" and current_todos:
        target = st.selectbox("選択", current_todos, format_func=lambda x: f"{x['title']}")
        if st.button("🗑️ 削除"):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()
        if st.button("✅ 完了/未完了を切り替え"):
            supabase.table("todos").update({"is_complete": not target['is_complete']}).eq("id", target['id']).execute()
            st.rerun()

# --- メイン：カレンダー表示 ---
st.title("📅 カテゴリ別マイカレンダー")
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in current_todos:
    prefix = "✅ " if item['is_complete'] else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": item['start_at'],
        "backgroundColor": "#D3D3D3" if item['is_complete'] else colors.get(item['category'], "#3D3333"),
    })

cal_options = {
    "editable": "true",
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
}
state = calendar(events=events, options=cal_options)

# --- ドラッグ後の更新 ---
if state.get("eventChange"):
    new_start = state["eventChange"]["event"]["start"]
    target_id = state["eventChange"]["event"]["id"]
    supabase.table("todos").update({"start_at": new_start}).eq("id", target_id).execute()
    st.toast("予定を移動しました！")

# --- リマインダー表示 ---
st.divider()
st.subheader("🔔 リマインダー")
upcoming = [r for r in current_todos if r['reminder_at'] and not r['is_complete']]
for r in sorted(upcoming, key=lambda x: x['reminder_at'])[:3]:
    st.info(f"📅 {r['reminder_at']} ： {r['title']}")
