import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# --- 接続設定 ---
url = st.secrets["url"]
key = st.secrets["key"]
supabase = create_client(url, key)

st.set_page_config(page_title="Advanced Task Calendar", layout="wide")

# --- ログイン機能（前回同様） ---
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
    rules = {
        "テスト": timedelta(weeks=-2),
        "課題": timedelta(days=-3),
        "遊び": timedelta(days=-1),
        "バイト": timedelta(days=-1)  # バイトは1日前
    }
    if category == "日用品":
        return event_datetime + relativedelta(months=1)
    return event_datetime + rules.get(category, timedelta(0))

# --- 1. サイドバー：予定の追加・管理 ---
with st.sidebar:
    st.title(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト"):
        del st.session_state.user
        st.rerun()
    
    st.divider()
    mode = st.radio("操作選択", ["新規追加", "編集・削除"])
    
    # ユーザーのデータ取得
    response = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    todos_df = response.data

    if mode == "新規追加":
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            col_d, col_t = st.columns(2)
            event_date = col_d.date_input("日付")
            event_time = col_t.time_input("時間", value=datetime.strptime("10:00", "%H:%M").time())
            cat = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            
            # --- 保存処理の部分（修正案） ---
if st.form_submit_button("保存"):
   　　　　 # 日付と時間を結合して、ISO形式（Supabaseが読み取れる形式）にする
    full_datetime = datetime.combine(event_date, event_time)
    
    data_to_insert = {
        "title": title,
        "start_at": full_datetime.isoformat(), # ここを start ではなく start_at に
        "category": cat,
        "reminder_at": rem.strftime('%Y-%m-%d') if rem else None,
        "user_id": user_id,
        "is_complete": False
    }
    
    # 保存実行
    supabase.table("todos").insert(data_to_insert).execute()
    st.success("保存しました！")
    st.rerun()
    elif mode == "編集・削除" and todos_df:
        target = st.selectbox("予定を選択", todos_df, format_func=lambda x: f"{x['title']} ({x['start_at'][:10]})")
        if st.button("🗑️ 削除"):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()
        if st.button("✅ 完了/未完了を切り替え"):
            supabase.table("todos").update({"is_complete": not target['is_complete']}).eq("id", target['id']).execute()
            st.rerun()

# --- 2. メイン：カレンダー表示 ---
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in todos_df:
    prefix = "✅ " if item['is_complete'] else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": item['start_at'],
        "backgroundColor": "#D3D3D3" if item['is_complete'] else colors.get(item['category'], "#3D3333"),
        "borderColor": "transparent"
    })

calendar_options = {
    "editable": "true",  # ドラッグ＆ドロップを有効化
    "selectable": "true",
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "initialView": "dayGridMonth",
}

# カレンダーの描画とイベント取得
state = calendar(events=events, options=calendar_options)

# --- 3. ドラッグ＆ドロップ後のデータ更新 ---
if state.get("eventClick"):
    st.toast(f"選択中: {state['eventClick']['event']['title']}")

if state.get("eventChange"):
    # 移動後の新しい日付を取得
    new_start = state["eventChange"]["event"]["start"]
    event_id = state["eventChange"]["event"]["id"]
    
    # Supabaseを更新
    supabase.table("todos").update({"start_at": new_start}).eq("id", event_id).execute()
    st.toast("予定を移動しました！")
    # リマインダー日の再計算などは省略していますが、必要に応じてここに追加可能です

# --- 4. 足元のリマインダー表示 ---
st.divider()
st.subheader("🔔 近日のリマインダー")
upcoming = [r for r in todos_df if r['reminder_at'] and not r['is_complete']]
for r in sorted(upcoming, key=lambda x: x['reminder_at'])[:5]:
    st.caption(f"📅 {r['reminder_at']} に通知予定： {r['title']}")
