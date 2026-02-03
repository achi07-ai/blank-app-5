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
    st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
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
            start_at_raw = item['start_at']
            start_dt = datetime.fromisoformat(start_at_raw).astimezone(JST)
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
        conf_pw = st.text_input("確認用",
