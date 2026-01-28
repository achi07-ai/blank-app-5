import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta, time
from dateutil.relativedelta import relativedelta

# --- 1. 接続設定 ---
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Secretsの設定を確認してください: {e}")
    st.stop()

st.set_page_config(page_title="Advanced Task Calendar", layout="wide")

# --- 2. ログイン・認証機能 ---
if "user" not in st.session_state:
    st.title("🔐 ログイン / 新規登録")
    email = st.text_input("メールアドレス")
    password = st.text_input("パスワード", type="password")
    
    col1, col2 = st.columns(2)
    if col1.button("ログイン", use_container_width=True):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception as e:
            st.error(f"ログイン失敗: {e}")
            
    if col2.button("新規登録", use_container_width=True):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("登録しました。そのままログインしてください。")
        except Exception as e:
            st.error(f"登録失敗: {e}")
    st.stop()

user_id = st.session_state.user.id

# --- 3. 便利関数（リマインダー・データ取得） ---
def calculate_reminder(event_datetime, category):
    rules = {
        "テスト": timedelta(weeks=-2),
        "課題": timedelta(days=-3),
        "遊び": timedelta(days=-1),
        "バイト": timedelta(days=-1)
    }
    if category == "日用品":
        return event_datetime + relativedelta(months=1)
    return event_datetime + rules.get(category, timedelta(0))

def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

# --- 4. サイドバー操作エリア ---
current_todos = get_my_todos()

with st.sidebar:
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()
    
    st.divider()
    mode = st.radio("操作メニュー", ["予定を追加", "編集・削除"])

    if mode == "予定を追加":
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            event_date = st.date_input("日付", datetime.now())
            
            t_col1, t_col2 = st.columns(2)
            start_t = t_col1.time_input("開始時間", value=time(10, 0))
            end_t = t_col2.time_input("終了時間", value=time(11, 0))
            
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            
            if st.form_submit_button("保存", use_container_width=True):
                if title:
                    start_dt = datetime.combine(event_date, start_t)
                    end_dt = datetime.combine(event_date, end_t)
                    
                    if end_dt <= start_dt:
                        st.error("終了時間は開始より後にしてください")
                    else:
                        rem = calculate_reminder(start_dt, cat)
                        supabase.table("todos").insert({
                            "user_id": user_id, "title": title, "category": cat,
                            "start_at": start_dt.isoformat(), "end_at": end_dt.isoformat(),
                            "reminder_at": rem.strftime('%Y-%m-%d') if rem else None
                        }).execute()
                        st.rerun()

    elif mode == "編集・削除" and current_todos:
        target = st.selectbox("対象を選択", current_todos, format_func=lambda x: f"{x['title']}")
        if st.button("🗑️ 削除", use_container_width=True):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()
        
        is_done = st.checkbox("完了済み", value=target.get('is_complete', False))
        if st.button("ステータスを更新", use_container_width=True):
            supabase.table("todos").update({"is_complete": is_done}).eq("id", target['id']).execute()
            st.rerun()

# --- 5. メイン画面：カレンダー表示 ---
st.title("📅 カテゴリ別マイカレンダー")

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
        "borderColor": "transparent"
    })

# --- カレンダーの表示詳細設定 ---
cal_options = {
    "editable": "true",
    "selectable": "true",
    "headerToolbar": {
        "left": "today prev,next",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    },
    "initialView": "dayGridMonth",
    "displayEventTime": True,      # 月表示でも時間を表示
    "displayEventEnd": True,       # 終了時間も表示
    "eventTimeFormat": {           # 日本で馴染みのある24時間表記に設定
        "hour": "2-digit",
        "minute": "2-digit",
        "hour12": False
    },
    "slotMinTime": "06:00:00",     # 朝6時から表示
    "slotMaxTime": "24:00:00",     # 夜12時まで表示
}

state = calendar(events=events, options=cal_options)

# --- 6. ドラッグ＆ドロップ時のデータ更新 ---
if state.get("eventChange"):
    target_id = state["eventChange"]["event"]["id"]
    new_start = state["eventChange"]["event"]["start"]
    new_end = state["eventChange"]["event"].get("end")
    
    update_vals = {"start_at": new_start}
    if new_end:
        update_vals["end_at"] = new_end
        
    supabase.table("todos").update(update_vals).eq("id", target_id).execute()
    st.toast("日時を更新しました")

# --- 7. リマインダー通知 ---
st.divider()
st.subheader("🔔 近日のリマインダー")
upcoming = [r for r in current_todos if r['reminder_at'] and not r.get('is_complete')]
if upcoming:
    for r in sorted(upcoming, key=lambda x: x['reminder_at'])[:3]:
        st.info(f"⏰ **{r['reminder_at']}** ： {r['category']} 「{r['title']}」")
else:
    st.caption("現在、近いリマインダーはありません。")
