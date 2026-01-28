import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta, time
from dateutil.relativedelta import relativedelta

# --- 1. 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="Advanced Calendar", layout="wide")

# --- 2. ログイン機能 ---
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

# --- 3. リマインダー計算ロジック ---
def calculate_reminder(event_datetime, category):
    rules = {"テスト": timedelta(weeks=-2), "課題": timedelta(days=-3), "遊び": timedelta(days=-1), "バイト": timedelta(days=-1)}
    if category == "日用品": return event_datetime + relativedelta(months=1)
    return event_datetime + rules.get(category, timedelta(0))

# --- データの取得関数 ---
def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

# --- 4. サイドバー操作 ---
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
            event_date = st.date_input("日付", datetime.now())
            
            st.write("時間設定")
            t_col1, t_col2 = st.columns(2)
            start_time = t_col1.time_input("開始", value=time(10, 0))
            end_time = t_col2.time_input("終了", value=time(11, 0))
            
            cat = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            
            if st.form_submit_button("保存"):
                if title:
                    start_dt = datetime.combine(event_date, start_time)
                    end_dt = datetime.combine(event_date, end_time)
                    
                    if end_dt <= start_dt:
                        st.error("終了時間は開始時間より後に設定してください")
                    else:
                        rem = calculate_reminder(start_dt, cat)
                        supabase.table("todos").insert({
                            "user_id": user_id,
                            "title": title,
                            "category": cat,
                            "start_at": start_dt.isoformat(),
                            "end_at": end_dt.isoformat(),
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

# --- 5. メイン：カレンダー表示 ---
st.title("📅 カテゴリ別マイカレンダー")
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in current_todos:
    prefix = "✅ " if item['is_complete'] else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": item['start_at'],
        "end": item.get('end_at'), # 終了時間を追加
        "backgroundColor": "#D3D3D3" if item['is_complete'] else colors.get(item['category'], "#3D3333"),
    })

cal_options = {
    "editable": "true",
    "selectable": "true",
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "slotMinTime": "06:00:00", # 表示開始時間
    "slotMaxTime": "24:00:00", # 表示終了時間
}
state = calendar(events=events, options=cal_options)

# --- 6. ドラッグ＆リサイズ後の更新 ---
# eventChangeは移動(ドラッグ)だけでなく、時間の長さ変更(リサイズ)も検知します
if state.get("eventChange"):
    new_start = state["eventChange"]["event"]["start"]
    new_end = state["eventChange"]["event"].get("end")
    target_id = state["eventChange"]["event"]["id"]
    
    update_data = {"start_at": new_start}
    if new_end:
        update_data["end_at"] = new_end
        
    supabase.table("todos").update(update_data).eq("id", target_id).execute()
    st.toast("予定を更新しました！")

# --- 7. リマインダー表示 ---
st.divider()
st.subheader("🔔 近日のリマインダー")
upcoming = [r for r in current_todos if r['reminder_at'] and not r['is_complete']]
for r in sorted(upcoming, key=lambda x: x['reminder_at'])[:3]:
    st.info(f"📅 {r['reminder_at']} ： {r['title']}")
