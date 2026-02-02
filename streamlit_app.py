import streamlit as st
from supabase import create_client
from streamlit_calendar import calendar
from datetime import datetime, timedelta, time
import pytz
import extra_streamlit_components as stx

# --- 1. 接続設定 ---
try:
    url = st.secrets["url"]
    key = st.secrets["key"]
    supabase = create_client(url, key)
except Exception as e:
    st.error(f"Secretsの設定を確認してください: {e}")
    st.stop()

APP_NAME = "マネたいむ。"
st.set_page_config(page_title=APP_NAME, layout="wide")

# Cookieマネージャーの初期化 (キャッシュして安定化)
@st.cache_resource
def get_cookie_manager():
    return stx.CookieManager()

cookie_manager = get_cookie_manager()

# 日本標準時 (JST) を定義
JST = pytz.timezone('Asia/Tokyo')

# --- 2. カスタムCSS ---
st.markdown(f"""
    <style>
    .main-title {{ font-size: 3rem !important; font-weight: 800 !important; color: #9B59B6; text-shadow: 2px 2px 4px rgba(0,0,0,0.1); margin-bottom: 0px; }}
    .sub-title {{ font-size: 1.1rem; color: #666; margin-bottom: 2rem; }}
    .fc-event-title {{ font-weight: bold !important; white-space: pre-wrap !important; font-size: 0.9em !important; padding: 4px !important; line-height: 1.2 !important; }}
    .fc-daygrid-day-frame {{ min-height: 120px !important; }}
    .fc-event {{ cursor: pointer; }}
    .salary-box {{ background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #9B59B6; margin-bottom: 10px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 便利関数 ---
def calculate_reminder(event_date, category):
    rules = { "テスト": timedelta(weeks=-2), "課題": timedelta(days=-3), "遊び": timedelta(days=-1), "バイト": timedelta(days=-1), "日用品": timedelta(days=30) }
    reminder_dt = event_date + rules.get(category, timedelta(0))
    return reminder_dt.strftime('%Y-%m-%d')

# --- 4. ログイン・自動ログイン機能 ---
if "user" not in st.session_state:
    # Cookieの読み込み
    saved_id = cookie_manager.get("manetime_user_id")
    saved_email = cookie_manager.get("manetime_user_email")

    if saved_id and saved_email:
        # 自動ログイン成功
        class User:
            def __init__(self, id, email):
                self.id = id
                self.email = email
        st.session_state.user = User(saved_id, saved_email)
        st.rerun()
    else:
        # ログイン画面の表示
        st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
        st.markdown("<p class='sub-title'>〜 時間とお金をスマートに管理 〜</p>", unsafe_allow_html=True)
        
        email = st.text_input("メールアドレス", key="login_email")
        password = st.text_input("パスワード", type="password", key="login_pw")
        
        c1, c2 = st.columns(2)
        if c1.button("ログイン", use_container_width=True, key="btn_login"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                cookie_manager.set("manetime_user_id", res.user.id, expires_at=datetime.now() + timedelta(days=30))
                cookie_manager.set("manetime_user_email", res.user.email, expires_at=datetime.now() + timedelta(days=30))
                st.rerun()
            except Exception as e: st.error(f"ログイン失敗: {e}")
            
        if c2.button("新規登録", use_container_width=True, key="btn_signup"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.info("登録しました。そのままログインしてください。")
            except Exception as e: st.error(f"登録失敗: {e}")
        st.stop()

# 以降はログイン済みの場合のみ実行される
user_id = st.session_state.user.id

# --- 5. データ取得 ---
@st.cache_data(ttl=60) # 1分間キャッシュしてパフォーマンス向上
def get_my_todos(uid):
    res = supabase.table("todos").select("*").eq("user_id", uid).execute()
    return res.data

current_todos = get_my_todos(user_id)

# --- 6. 給与計算・詳細ダイアログ・カレンダー描画 (以前と同様) ---
# ※ エラー回避のため各ボタンに key="xxx" を追加しています

def calculate_monthly_salary(todos, wage, fixed):
    v_salary = 0
    now = datetime.now(JST)
    for item in todos:
        if item['category'] == "バイト":
            start = datetime.fromisoformat(item['start_at']).astimezone(JST)
            if start.month == now.month and start.year == now.year:
                end = datetime.fromisoformat(item['end_at']).astimezone(JST)
                hours = (end - start).total_seconds() / 3600
                v_salary += hours * wage
    return int(v_salary + fixed)

@st.dialog("予定の詳細と編集")
def show_event_details(eid):
    item = next((x for x in current_todos if str(x['id']) == eid), None)
    if item:
        st.subheader(f"📝 {item['title']}")
        with st.form("edit_form"):
            new_title = st.text_input("予定名", value=item['title'])
            curr_s = datetime.fromisoformat(item['start_at']).astimezone(JST)
            curr_e = datetime.fromisoformat(item['end_at']).astimezone(JST)
            new_d = st.date_input("日付", curr_s.date())
            t1, t2 = st.columns(2)
            new_st = t1.time_input("開始", curr_s.time())
            new_et = t2.time_input("終了", curr_e.time())
            new_c = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"], 
                                 index=["テスト", "課題", "日用品", "遊び", "バイト", "その他"].index(item['category']))
            if st.form_submit_button("更新", use_container_width=True):
                ns = JST.localize(datetime.combine(new_d, new_st)).isoformat()
                ne = JST.localize(datetime.combine(new_d, new_et)).isoformat()
                supabase.table("todos").update({"title": new_title, "category": new_c, "start_at": ns, "end_at": ne}).eq("id", eid).execute()
                st.cache_data.clear()
                st.rerun()
        if st.button("🗑️ 削除", use_container_width=True, key=f"del_{eid}"):
            supabase.table("todos").delete().eq("id", eid).execute()
            st.cache_data.clear()
            st.rerun()

# --- 7. サイドバー ---
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト", use_container_width=True, key="sidebar_logout"):
        cookie_manager.delete("manetime_user_id")
        cookie_manager.delete("manetime_user_email")
        st.session_state.clear()
        st.rerun()
    
    st.divider()
    with st.expander("🔐 パスワード変更"):
        npw = st.text_input("新パスワード", type="password", key="new_pw_input")
        if st.button("更新", key="pw_update_btn"):
            supabase.auth.update_user({"password": npw})
            st.success("完了")

    st.divider()
    st.subheader("💰 給与設定")
    if "h_wage" not in st.session_state: st.session_state.h_wage = 1200
    if "f_salary" not in st.session_state: st.session_state.f_salary = 0
    st.session_state.h_wage = st.number_input("時給", value=st.session_state.h_wage, key="input_wage")
    st.session_state.f_salary = st.number_input("固定給", value=st.session_state.f_salary, key="input_fixed")

    st.divider()
    if st.toggle("新規予定を追加", key="toggle_add"):
        with st.form("add_form"):
            title = st.text_input("予定名")
            d = st.date_input("日付", datetime.now(JST).date())
            t1, t2 = st.columns(2)
            s_t, e_t = t1.time_input("開始", time(10, 0)), t2.time_input("終了", time(11, 0))
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            if st.form_submit_button("保存"):
                s_dt = JST.localize(datetime.combine(d, s_t)).isoformat()
                e_dt = JST.localize(datetime.combine(d, e_t)).isoformat()
                supabase.table("todos").insert({"user_id": user_id, "title": title, "category": cat, "start_at": s_dt, "end_at": e_dt, "is_complete": False}).execute()
                st.cache_data.clear()
                st.rerun()

# --- 8. メイン表示 ---
st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
salary = calculate_monthly_salary(current_todos, st.session_state.h_wage, st.session_state.f_salary)
st.markdown(f"<div class='salary-box'><p style='margin:0;'>💰 今月の見込み給与</p><h2 style='margin:0;'>¥{salary:,}</h2></div>", unsafe_allow_html=True)

events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}
for item in current_todos:
    ls = datetime.fromisoformat(item['start_at']).astimezone(JST).replace(tzinfo=None).isoformat()
    le = datetime.fromisoformat(item['end_at']).astimezone(JST).replace(tzinfo=None).isoformat()
    events.append({"id": str(item['id']), "title": f"[{item['category']}]\n{item['title']}", "start": ls, "end": le, "backgroundColor": colors.get(item['category'], "#3D3333"), "borderColor": "transparent"})

cal_options = {"editable": "true", "selectable": "true", "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"}, "initialView": "dayGridMonth", "locale": "ja", "dayMaxEvents": False, "contentHeight": "auto", "eventDisplay": "block", "displayEventTime": True, "displayEventEnd": True, "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False}}

state = calendar(events=events, options=cal_options, key="manetime_calendar")

if state.get("eventClick"):
    show_event_details(state["eventClick"]["event"]["id"])

if state.get("eventChange"):
    eid = state["eventChange"]["event"]["id"]
    ns = datetime.fromisoformat(state["eventChange"]["event"]["start"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    ne = datetime.fromisoformat(state["eventChange"]["event"]["end"].replace('Z', '+00:00')).astimezone(JST).isoformat() if state["eventChange"]["event"].get("end") else None
    upd = {"start_at": ns}
    if ne: upd["end_at"] = ne
    supabase.table("todos").update(upd).eq("id", eid).execute()
    st.cache_data.clear()
    st.rerun()
