import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta, time
import pytz

# --- 1. 接続設定 ---
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Secretsの設定を確認してください: {e}")
    st.stop()

st.set_page_config(page_title="Task Calendar Drag&Drop", layout="wide")

# 日本標準時 (JST) を定義
JST = pytz.timezone('Asia/Tokyo')

# --- 2. ログイン / 新規登録機能 ---
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
        except Exception as e: st.error(f"ログイン失敗: {e}")
    if col2.button("新規登録", use_container_width=True):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("登録しました。そのままログインしてください。")
        except Exception as e: st.error(f"登録失敗: {e}")
    st.stop()

user_id = st.session_state.user.id

# --- 3. データ取得 ---
def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

current_todos = get_my_todos()

# --- 4. サイドバー：操作エリア ---
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
            event_date = st.date_input("日付", datetime.now(JST).date())
            t_col1, t_col2 = st.columns(2)
            start_t = t_col1.time_input("開始", value=time(10, 0))
            end_t = t_col2.time_input("終了", value=time(11, 0))
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            
            if st.form_submit_button("保存", use_container_width=True):
                if title:
                    start_dt = JST.localize(datetime.combine(event_date, start_t))
                    end_dt = JST.localize(datetime.combine(event_date, end_t))
                    
                    supabase.table("todos").insert({
                        "user_id": user_id, "title": title, "category": cat,
                        "start_at": start_dt.isoformat(), "end_at": end_dt.isoformat(),
                        "is_complete": False
                    }).execute()
                    st.rerun()

    elif mode == "編集・削除" and current_todos:
        target = st.selectbox("予定を選択", current_todos, format_func=lambda x: f"{x['title']}")
        if st.button("🗑️ 予定を削除", use_container_width=True):
            supabase.table("todos").delete().eq("id", target['id']).execute()
            st.rerun()
        is_done = st.checkbox("完了済み", value=target.get('is_complete', False))
        if st.button("更新", use_container_width=True):
            supabase.table("todos").update({"is_complete": is_done}).eq("id", target['id']).execute()
            st.rerun()

# --- 5. メイン画面：カレンダー表示 ---
st.title("📅 カテゴリ別マイカレンダー")
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}

for item in current_todos:
    raw_start = datetime.fromisoformat(item['start_at'])
    raw_end = datetime.fromisoformat(item['end_at'])
    
    # 表示用にタイムゾーン情報を消去（時差ズレ防止）
    local_start = raw_start.astimezone(JST).replace(tzinfo=None)
    local_end = raw_end.astimezone(JST).replace(tzinfo=None)

    prefix = "✅ " if item.get('is_complete') else ""
    events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}] {item['title']}",
        "start": local_start.isoformat(),
        "end": local_end.isoformat(),
        "backgroundColor": "#D3D3D3" if item.get('is_complete') else colors.get(item['category'], "#3D3333"),
        "borderColor": "transparent"
    })

# ドラッグ＆ドロップを有効化するオプションを追加
cal_options = {
    "editable": "true", # これでドラッグ＆リサイズが可能になります
    "selectable": "true",
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "displayEventTime": True,
    "displayEventEnd": True,
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "locale": "ja"
}

# カレンダーの描画と状態取得
state = calendar(events=events, options=cal_options)

# --- 6. 重要：ドラッグ＆ドロップ後のデータベース更新処理 ---
if state.get("eventChange"):
    event_id = state["eventChange"]["event"]["id"]
    new_start_raw = state["eventChange"]["event"]["start"]
    new_end_raw = state["eventChange"]["event"].get("end")
    
    # エラー回避のポイント: 
    # fromisoformatで読み込む際、既にタイムゾーンがある場合はそのまま使い、
    # なければJSTを付与するように処理を変更します。
    
    def format_to_jst_iso(raw_time_str):
        if not raw_time_str:
            return None
        # 文字列の末尾が 'Z' の場合は、標準的なISO形式に置換
        clean_time = raw_time_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_time)
        # 日本時間に変換してISO形式で返す
        return dt.astimezone(JST).isoformat()

    update_data = {
        "start_at": format_to_jst_iso(new_start_raw)
    }
    
    if new_end_raw:
        update_data["end_at"] = format_to_jst_iso(new_end_raw)
        
    # Supabaseを更新
    try:
        supabase.table("todos").update(update_data).eq("id", event_id).execute()
        st.toast("予定を移動しました！")
        st.rerun()
    except Exception as e:
        st.error(f"更新エラー: {e}")
