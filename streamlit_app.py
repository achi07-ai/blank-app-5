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

# アプリ名の設定
APP_NAME = "マネたいむ。"
st.set_page_config(page_title=APP_NAME, layout="wide")

# 日本標準時 (JST) を定義
JST = pytz.timezone('Asia/Tokyo')

# --- 2. カスタムCSS ---
st.markdown(f"""
    <style>
    .main-title {{
        font-size: 3rem !important;
        font-weight: 800 !important;
        color: #9B59B6;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 0px;
    }}
    .sub-title {{
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }}
    .fc-event-title {{
        font-weight: bold !important;
        white-space: pre-wrap !important;
        font-size: 0.9em !important;
        padding: 4px !important;
        line-height: 1.2 !important;
    }}
    .fc-daygrid-day-frame {{
        min-height: 120px !important;
    }}
    .fc-event {{
        cursor: pointer;
    }}
    .salary-box {{
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #9B59B6;
        margin-bottom: 10px;
    }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 便利関数 ---
def calculate_reminder(event_date, category):
    rules = {
        "テスト": timedelta(weeks=-2), "課題": timedelta(days=-3),
        "遊び": timedelta(days=-1), "バイト": timedelta(days=-1), "日用品": timedelta(days=30)
    }
    reminder_dt = event_date + rules.get(category, timedelta(0))
    return reminder_dt.strftime('%Y-%m-%d')

# --- 4. ログイン機能 ---
if "user" not in st.session_state:
    st.markdown(f<h1 class='main-title'>{APP_NAME}</h1>, unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>〜 時間とお金をスマートに管理 〜</p>", unsafe_allow_html=True)
    
    email = st.text_input("メールアドレス", key="login_email")
    password = st.text_input("パスワード", type="password", key="login_pw")
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

# --- 5. データ取得 ---
def get_my_todos():
    res = supabase.table("todos").select("*").eq("user_id", user_id).execute()
    return res.data

current_todos = get_my_todos()

# --- 6. 給与計算ロジック ---
def calculate_monthly_salary(todos, hourly_wage, fixed_salary):
    variable_salary = 0
    now = datetime.now(JST)
    for item in todos:
        if item['category'] == "バイト":
            start_dt = datetime.fromisoformat(item['start_at']).astimezone(JST)
            if start_dt.month == now.month and start_dt.year == now.year:
                end_dt = datetime.fromisoformat(item['end_at']).astimezone(JST)
                duration = end_dt - start_dt
                hours = duration.total_seconds() / 3600
                variable_salary += hours * hourly_wage
    return int(variable_salary + fixed_salary)

# --- 7. 詳細表示・編集・削除ダイアログ ---
@st.dialog("予定の詳細と編集")
def show_event_details(event_id):
    item = next((x for x in current_todos if str(x['id']) == event_id), None)
    if item:
        st.subheader(f"📝 {item['title']}")
        with st.form("edit_event_form"):
            new_title = st.text_input("予定名", value=item['title'])
            curr_start = datetime.fromisoformat(item['start_at']).astimezone(JST)
            curr_end = datetime.fromisoformat(item['end_at']).astimezone(JST)
            new_date = st.date_input("日付", curr_start.date())
            col_t1, col_t2 = st.columns(2)
            new_s_time = col_t1.time_input("開始", curr_start.time())
            new_e_time = col_t2.time_input("終了", curr_end.time())
            categories = ["テスト", "課題", "日用品", "遊び", "バイト", "その他"]
            new_cat = st.selectbox("カテゴリ", categories, index=categories.index(item['category']))
            
            if st.form_submit_button("内容を更新", use_container_width=True):
                new_start_dt = JST.localize(datetime.combine(new_date, new_s_time))
                new_end_dt = JST.localize(datetime.combine(new_date, new_e_time))
                rem_date = calculate_reminder(new_date, new_cat)
                supabase.table("todos").update({
                    "title": new_title, "category": new_cat,
                    "start_at": new_start_dt.isoformat(), "end_at": new_end_dt.isoformat(),
                    "reminder_at": rem_date
                }).eq("id", event_id).execute()
                st.rerun()
        st.divider()
        if st.button("🗑️ この予定を削除する", use_container_width=True, type="secondary"):
            supabase.table("todos").delete().eq("id", event_id).execute()
            st.rerun()

# --- 8. サイドバー (修正版) ---
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト", use_container_width=True):
        supabase.auth.sign_out()
        del st.session_state.user
        st.rerun()
    
    st.divider()
    with st.expander("🔐 パスワードを変更"):
        new_pw = st.text_input("新しいパスワード", type="password")
        conf_pw = st.text_input("確認用", type="password")
        if st.button("更新", use_container_width=True):
            if len(new_pw) >= 6 and new_pw == conf_pw:
                supabase.auth.update_user({"password": new_pw})
                st.success("更新完了！")
            else: st.error("不備があります")

    st.divider()
    st.subheader("💰 給与設定")
    if "hourly_wage" not in st.session_state: st.session_state.hourly_wage = 1200
    if "fixed_salary" not in st.session_state: st.session_state.fixed_salary = 0
    
    col_wage, col_fixed = st.columns(2)
    st.session_state.hourly_wage = col_wage.number_input("時給 (円)", value=st.session_state.hourly_wage, step=10)
    st.session_state.fixed_salary = col_fixed.number_input("固定給 (円)", value=st.session_state.fixed_salary, step=1000)
    
    if st.button("給料設定を保存", use_container_width=True):
        st.success("セッションに保存しました")

    st.divider()
    if st.toggle("新規予定を追加"):
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            event_date = st.date_input("日付", datetime.now(JST).date())
            t1, t2 = st.columns(2)
            start_t, end_t = t1.time_input("開始", value=time(10, 0)), t2.time_input("終了", value=time(11, 0))
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            if st.form_submit_button("保存", use_container_width=True):
                if title:
                    start_dt = JST.localize(datetime.combine(event_date, start_t))
                    end_dt = JST.localize(datetime.combine(event_date, end_t))
                    rem_date = calculate_reminder(event_date, cat)
                    supabase.table("todos").insert({
                        "user_id": user_id, "title": title, "category": cat,
                        "start_at": start_dt.isoformat(), "end_at": end_dt.isoformat(),
                        "reminder_at": rem_date, "is_complete": False
                    }).execute()
                    st.rerun()

# --- 9. メイン画面：給与 & カレンダー (修正版) ---
st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)

monthly_salary = calculate_monthly_salary(current_todos, st.session_state.hourly_wage, st.session_state.fixed_salary)
col_a, col_b = st.columns([1, 2])
with col_a:
    st.markdown(f"""<div class="salary-box">
        <p style='margin:0; font-size:0.9em; color:#666;'>💰 今月の見込み給与 (時給+固定)</p>
        <h2 style='margin:0; color:#9B59B6;'>¥{monthly_salary:,}</h2>
    </div>""", unsafe_allow_html=True)

with col_b:
    upcoming = [r for r in current_todos if r.get('reminder_at') and not r.get('is_complete')]
    if upcoming:
        today_str = datetime.now(JST).strftime('%Y-%m-%d')
        future = [r for r in upcoming if r['reminder_at'] >= today_str]
        if future:
            r = sorted(future, key=lambda x: x['reminder_at'])[0]
            st.warning(f"🔔 リマインド: {r['reminder_at']} [{r['category']}] {r['title']}")

# イベントデータの準備（タイムゾーンとallDay属性の修正）
formatted_events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}
for item in current_todos:
    s_dt = datetime.fromisoformat(item['start_at']).astimezone(JST)
    e_dt = datetime.fromisoformat(item['end_at']).astimezone(JST)
    prefix = "✅ " if item.get('is_complete') else ""
    
    formatted_events.append({
        "id": str(item['id']),
        "title": f"{prefix}[{item['category']}]\n{item['title']}",
        "start": s_dt.isoformat(),
        "end": e_dt.isoformat(),
        "backgroundColor": "#D3D3D3" if item.get('is_complete') else colors.get(item['category'], "#3D3333"),
        "borderColor": "transparent",
        "allDay": False # week/dayビューで時間枠に表示するために必須
    })

cal_options = {
    "editable": "true",
    "selectable": "true",
    "headerToolbar": {
        "left": "today prev,next",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    },
    "initialView": "dayGridMonth",
    "locale": "ja",
    "allDaySlot": False,
    "slotMinTime": "06:00:00",
    "slotMaxTime": "24:00:00",
    "contentHeight": "auto",
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False}
}

state = calendar(events=formatted_events, options=cal_options, key="manetime_cal")

# --- 10. イベント処理 ---
if state.get("eventClick"):
    show_event_details(state["eventClick"]["event"]["id"])

if state.get("eventChange"):
    event_id = state["eventChange"]["event"]["id"]
    new_s = datetime.fromisoformat(state["eventChange"]["event"]["start"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    new_e = datetime.fromisoformat(state["eventChange"]["event"]["end"].replace('Z', '+00:00')).astimezone(JST).isoformat() if state["eventChange"]["event"].get("end") else None
    
    upd = {"start_at": new_s}
    if new_e: upd["end_at"] = new_e
    
    supabase.table("todos").update(upd).eq("id", event_id).execute()
    st.toast("予定を移動しました！")
    st.rerun()
