import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta
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
        except: st.error("ログインに失敗しました。メールアドレスとパスワードを確認してください。")
    if col2.button("新規登録"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("登録リクエストを送信しました。そのままログインをお試しください。")
        except: st.error("登録に失敗しました。")
    st.stop()

user_id = st.session_state.user.id

# --- 3. リマインダー計算ロジック ---
def calculate_reminder(event_datetime, category):
    rules = {
        "テスト": timedelta(weeks=-2),
        "課題": timedelta(days=-3),
        "遊び": timedelta(days=-1),
        "バイト": timedelta(days=-1)
    }
    if category == "日用品":
        return event_datetime + relativedelta(months=1)
    # 予定日当日にリマインダーを出す場合は timedelta(0)
    return event_datetime + rules.get(category, timedelta(0))

# --- 4. データの取得 ---
def get_todos():
    response = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return response.data

todos = get_todos()

# --- 5. サイドバー：予定の追加・管理 ---
with st.sidebar:
    st.title(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト"):
        del st.session_state.user
        st.rerun()
    
    st.divider()
    mode = st.radio("操作選択", ["新規追加", "編集・削除"])

    if mode == "新規追加":
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            col_d, col_t = st.columns(2)
            event_date = col_d.date_input("日付", datetime.now())
            event_time = col_t.time_input("時間", value=datetime.strptime("10:00", "%H:%M").time())
            cat = st.selectbox("項目", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            
            if st.form_submit_button("保存"):
                if title:
                    full_datetime = datetime.combine(event_date, event_time)
                    rem = calculate_reminder(full_datetime, cat)
                    
                    # 修正ポイント: 全て 'start_at' カラムに統一して送信
                    data = {
                        "title": title,
                        "start_at": full_datetime.isoformat(),
                        "category": cat,
                        "reminder_at": rem.strftime('%Y-%m-%d') if rem else None,
                        "user_id": user_id,
                        "is_complete": False
                    }
                    supabase.table("todos").insert(data).execute()
                    st.success("保存完了！")
                    st.rerun()
                else:
                    st.warning("予定名を入力してください")

    elif mode == "編集・削除" and todos:
        target = st.selectbox("予定を選択", todos, format_func=lambda x: f"{x['title']} ({x['start_at'][:10]})")
        if st.button("🗑️ この予定を削除"):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()
        
        is_done = st.checkbox("完了済みとしてマーク", value=target.get('is_complete', False))
        if st.button("ステータスを更新"):
            supabase.table("todos").update({"is_complete": is_done}).eq("id", target['id']).execute()
            st.rerun()

# --- 6. メイン画面：カレンダー ---
st.title("📅 カテゴリ別マイカレンダー")

events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in todos:
    prefix = "✅ " if item.get('is_complete') else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": item['start_at'],  # 時間情報を含む
        "backgroundColor": "#D3D3D3" if item.get('is_complete') else colors.get(item['category'], "#3D3333"),
        "borderColor": "transparent"
    })

calendar_options = {
    "editable": "true",
    "selectable": "true",
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "initialView": "dayGridMonth",
    "navLinks": "true",
}

state = calendar(events=events, options=calendar_options)

# --- 7. ドラッグ＆ドロップの検知と更新 ---
if state.get("eventChange"):
    event_id = state["eventChange"]["event"]["id"]
    new_start = state["eventChange"]["event"]["start"]
    
    # データベース側の日時を更新
    supabase.table("todos").update({"start_at": new_start}).eq("id", event_id).execute()
    st.toast("予定を移動しました！")

# --- 8. リマインダー一覧の表示 ---
st.divider()
st.subheader("🔔 近日のリマインダー")
upcoming = [r for r in todos if r['reminder_at'] and not r.get('is_complete')]
if upcoming:
    # リマインダー日が近い順に5件表示
    for r in sorted(upcoming, key=lambda x: x['reminder_at'])[:5]:
        st.info(f"⏰ **{r['reminder_at']}**：{r['category']} 「{r['title']}」")
else:
    st.write("現在、近い予定のリマインダーはありません。")
