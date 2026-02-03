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

APP_NAME = "マネたいむ。"
st.set_page_config(page_title=APP_NAME, layout="wide")
JST = pytz.timezone('Asia/Tokyo')

# --- 2. カスタムCSS（土日色付け等） ---
st.markdown(f"""
    <style>
    .main-title {{ font-size: 3rem !important; font-weight: 800 !important; color: #9B59B6; text-shadow: 2px 2px 4px rgba(0,0,0,0.1); margin-bottom: 0px; }}
    .sub-title {{ font-size: 1.1rem; color: #666; margin-bottom: 2rem; }}
    .fc-event-title {{ font-weight: bold !important; white-space: pre-wrap !important; font-size: 0.85em !important; padding: 2px !important; }}
    .fc-daygrid-day-frame {{ min-height: 120px !important; }}
    .fc-day-sat {{ background-color: #eaf4ff !important; }}
    .fc-day-sun {{ background-color: #fff0f0 !important; }}
    .salary-box {{ background-color: #f8f9fa; padding: 20px; border-radius: 12px; border-left: 6px solid #9B59B6; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 便利関数 ---
def calculate_reminder(event_date, category):
    rules = {
        "テスト": timedelta(weeks=-2), "課題": timedelta(days=-3),
        "遊び": timedelta(days=-1), "バイト": timedelta(days=-1), "日用品": timedelta(days=30)
    }
    return (event_date + rules.get(category, timedelta(0))).strftime('%Y-%m-%d')

# --- 4. ログイン / 新規登録フロー ---
if "user" not in st.session_state:
    st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
    auth_mode = st.radio("メニュー", ["ログイン", "新規ユーザー登録"], horizontal=True, key="auth_selector")
    
    email = st.text_input("メールアドレス", key="auth_email")
    password = st.text_input("パスワード", type="password", key="auth_pw")
    
    if auth_mode == "ログイン":
        if st.button("ログインする", use_container_width=True, key="login_submit"):
            try:
                res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except: st.error("ログインに失敗しました。")
    else:
        if st.button("アカウントを作成する", use_container_width=True, key="signup_submit"):
            try:
                supabase.auth.sign_up({"email": email, "password": password})
                st.success("登録完了！ログイン画面からログインしてください。")
            except: st.error("登録に失敗しました。")
    st.stop()

user_id = st.session_state.user.id

# --- 5. 設定・データ取得 (永続化) ---
def get_settings():
    try:
        res = supabase.table("settings").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
        else:
            initial = {"user_id": user_id, "hourly_wage": 1200, "fixed_salary": 0}
            supabase.table("settings").upsert(initial).execute()
            return initial
    except:
        return {"user_id": user_id, "hourly_wage": 1200, "fixed_salary": 0}

settings = get_settings()
current_todos = supabase.table("todos").select("*").eq("user_id", user_id).execute().data

# --- 6. 詳細ダイアログ ---
@st.dialog("予定の編集")
def show_event_details(event_id):
    item = next((x for x in current_todos if str(x['id']) == event_id), None)
    if item:
        with st.form(f"edit_form_{event_id}"):
            title = st.text_input("予定名", value=item['title'])
            curr_s = datetime.fromisoformat(item['start_at']).astimezone(JST)
            curr_e = datetime.fromisoformat(item['end_at']).astimezone(JST)
            d = st.date_input("日付", curr_s.date())
            t1, t2 = st.columns(2)
            st_t, et_t = t1.time_input("開始", curr_s.time()), t2.time_input("終了", curr_e.time())
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"], 
                               index=["テスト", "課題", "日用品", "遊び", "バイト", "その他"].index(item['category']))
            done = st.checkbox("完了済み (✅)", value=item.get('is_complete', False))
            
            if st.form_submit_button("更新"):
                ns = JST.localize(datetime.combine(d, st_t)).isoformat()
                ne = JST.localize(datetime.combine(d, et_t)).isoformat()
                supabase.table("todos").update({
                    "title": title, "category": cat, "start_at": ns, "end_at": ne,
                    "reminder_at": calculate_reminder(d, cat), "is_complete": done
                }).eq("id", event_id).execute()
                st.rerun()
        if st.button("🗑️ 削除", use_container_width=True, key=f"del_btn_{event_id}"):
            supabase.table("todos").delete().eq("id", event_id).execute()
            st.rerun()

# --- 7. サイドバー ---
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.write(f"👤 {st.session_state.user.email}")
    if st.button("ログアウト", use_container_width=True, key="logout_btn_main"):
        supabase.auth.sign_out()
        if "user" in st.session_state: del st.session_state.user
        st.rerun()
    
    st.divider()
    st.subheader("💰 給与設定")
    new_h = st.number_input("時給", value=settings['hourly_wage'], step=10, key="wage_input_main")
    new_f = st.number_input("固定給", value=settings['fixed_salary'], step=1000, key="fixed_input_main")
    if st.button("設定を保存", use_container_width=True, key="save_settings_btn"):
        supabase.table("settings").upsert({"user_id": user_id, "hourly_wage": new_h, "fixed_salary": new_f}).execute()
        st.success("保存しました！")
        st.rerun()

    st.divider()
    if st.toggle("新規予定を追加", key="add_toggle"):
        with st.form("add_form", clear_on_submit=True):
            title = st.text_input("予定名")
            d = st.date_input("日付", datetime.now(JST).date())
            t1, t2 = st.columns(2)
            s_t, e_t = t1.time_input("開始", time(10, 0)), t2.time_input("終了", time(11, 0))
            cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"])
            if st.form_submit_button("保存"):
                s_dt = JST.localize(datetime.combine(d, s_t)).isoformat()
                e_dt = JST.localize(datetime.combine(d, e_t)).isoformat()
                supabase.table("todos").insert({
                    "user_id": user_id, "title": title, "category": cat, "start_at": s_dt, "end_at": e_dt,
                    "reminder_at": calculate_reminder(d, cat), "is_complete": False
                }).execute()
                st.rerun()

# --- 8. メイン画面 ---
st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)

# リマインダー通知
upcoming = [r for r in current_todos if r.get('reminder_at') and not r.get('is_complete')]
if upcoming:
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    alerts = [r for r in upcoming if r['reminder_at'] <= today_str]
    for r in alerts:
        st.warning(f"🔔 **リマインド**: {r['title']} ([{r['category']}] 期限間近です)")

# 給与計算
var_s, hours = 0, 0
now = datetime.now(JST)
for item in current_todos:
    if item['category'] == "バイト":
        start_dt = datetime.fromisoformat(item['start_at']).astimezone(JST)
        if start_dt.month == now.month and start_dt.year == now.year:
            h = (datetime.fromisoformat(item['end_at']).astimezone(JST) - start_dt).total_seconds() / 3600
            hours += h
            var_s += h * settings['hourly_wage']

st.markdown(f"""
    <div class="salary-box">
        <h2 style='margin:0; color:#9B59B6;'>今月の見込み合計: ¥{int(var_s) + settings['fixed_salary']:,}</h2>
        <p style='margin:0; color:#666;'>内訳: 固定 ¥{settings['fixed_salary']:,} + バイト代 ¥{int(var_s):,} ({round(hours, 1)}時間)</p>
    </div>
""", unsafe_allow_html=True)

# カレンダー表示設定
events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}
for item in current_todos:
    done = item.get('is_complete', False)
    events.append({
        "id": str(item['id']),
        "title": f"{'✅' if done else ''}[{item['category']}] {item['title']}",
        "start": datetime.fromisoformat(item['start_at']).astimezone(JST).replace(tzinfo=None).isoformat(),
        "end": datetime.fromisoformat(item['end_at']).astimezone(JST).replace(tzinfo=None).isoformat(),
        "backgroundColor": "#bdc3c7" if done else colors.get(item['category'], "#3D3333"),
        "allDay": False
    })

cal_options = {
    "headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"},
    "locale": "ja", "slotMinTime": "00:00:00", "slotMaxTime": "24:00:00", "editable": True, "eventDisplay": "block",
}
state = calendar(events=events, options=cal_options, key="manetime_final_calendar")

if state.get("eventClick"): show_event_details(state["eventClick"]["event"]["id"])
if state.get("eventChange"):
    eid = state["eventChange"]["event"]["id"]
    new_s = datetime.fromisoformat(state["eventChange"]["event"]["start"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    new_e = datetime.fromisoformat(state["eventChange"]["event"]["end"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    supabase.table("todos").update({"start_at": new_s, "end_at": new_e}).eq("id", eid).execute()
    st.rerun()
