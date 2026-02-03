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

# --- 2. カスタムCSS ---
st.markdown(f"""
    <style>
    .main-title {{ font-size: 3rem !important; font-weight: 800 !important; color: #9B59B6; text-shadow: 2px 2px 4px rgba(0,0,0,0.1); margin-bottom: 0px; }}
    .sub-title {{ font-size: 1.1rem; color: #666; margin-bottom: 2rem; }}
    .fc-event-title {{ font-weight: bold !important; white-space: pre-wrap !important; font-size: 0.9em !important; padding: 4px !important; line-height: 1.2 !important; }}
    .fc-daygrid-day-frame {{ min-height: 120px !important; }}
    .fc-event {{ cursor: pointer; border: none !important; }}
    .fc-day-sat {{ background-color: #eaf4ff !important; }}
    .fc-day-sun {{ background-color: #fff0f0 !important; }}
    .salary-box {{ background-color: #f8f9fa; padding: 20px; border-radius: 12px; border-left: 6px solid #9B59B6; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
    .salary-detail {{ font-size: 0.85rem; color: #555; margin-top: 5px; }}
    </style>
""", unsafe_allow_html=True)

# --- 3. 便利関数 ---
def calculate_reminder(event_date, category):
    rules = { "テスト": timedelta(weeks=-2), "課題": timedelta(days=-3), "遊び": timedelta(days=-1), "バイト": timedelta(days=-1), "日用品": timedelta(days=30) }
    return (event_date + rules.get(category, timedelta(0))).strftime('%Y-%m-%d')

# --- 4. ログイン機能 ---
if "user" not in st.session_state:
    st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown("<p class='sub-title'>〜 時間とお金をスマートに管理 〜</p>", unsafe_allow_html=True)
    email = st.text_input("メールアドレス", key="login_email")
    password = st.text_input("パスワード", type="password", key="login_pw")
    c1, c2 = st.columns(2)
    if c1.button("ログイン", use_container_width=True, key="login_btn"):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state.user = res.user
            st.rerun()
        except Exception as e: st.error(f"失敗: {e}")
    if c2.button("新規登録", use_container_width=True, key="signup_btn"):
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            st.info("登録完了。ログインしてください。")
        except Exception as e: st.error(f"失敗: {e}")
    st.stop()

user_id = st.session_state.user.id

# --- 5. 設定取得 (安定化版) ---
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

# --- 6. 給与計算 ---
def get_salary_info(todos, hourly_wage, fixed_salary):
    var_sal, hours = 0, 0
    now = datetime.now(JST)
    for item in todos:
        if item['category'] == "バイト":
            start_dt = datetime.fromisoformat(item['start_at']).astimezone(JST)
            if start_dt.month == now.month and start_dt.year == now.year:
                end_dt = datetime.fromisoformat(item['end_at']).astimezone(JST)
                h = (end_dt - start_dt).total_seconds() / 3600
                hours += h
                var_sal += h * hourly_wage
    return int(var_sal), int(fixed_salary), round(hours, 1)

# --- 7. 詳細ダイアログ ---
@st.dialog("予定の編集")
def show_event_details(event_id):
    item = next((x for x in current_todos if str(x['id']) == event_id), None)
    if item:
        with st.form("edit_form"):
            new_title = st.text_input("予定名", value=item['title'])
            curr_s = datetime.fromisoformat(item['start_at']).astimezone(JST)
            curr_e = datetime.fromisoformat(item['end_at']).astimezone(JST)
            new_date = st.date_input("日付", curr_s.date())
            t1, t2 = st.columns(2)
            new_st, new_et = t1.time_input("開始", curr_s.time()), t2.time_input("終了", curr_e.time())
            new_cat = st.selectbox("カテゴリ", ["テスト", "課題", "日用品", "遊び", "バイト", "その他"], 
                                   index=["テスト", "課題", "日用品", "遊び", "バイト", "その他"].index(item['category']))
            is_done = st.checkbox("完了済み (✅)", value=item.get('is_complete', False))
            if st.form_submit_button("更新"):
                ns = JST.localize(datetime.combine(new_date, new_st)).isoformat()
                ne = JST.localize(datetime.combine(new_date, new_et)).isoformat()
                supabase.table("todos").update({"title": new_title, "category": new_cat, "start_at": ns, "end_at": ne, "reminder_at": calculate_reminder(new_date, new_cat), "is_complete": is_done}).eq("id", event_id).execute()
                st.rerun()
        if st.button("🗑️ 削除", use_container_width=True, key=f"del_{event_id}"):
            supabase.table("todos").delete().eq("id", event_id).execute()
            st.rerun()

# --- 8. サイドバー ---
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    if st.button("ログアウト", key="logout_sidebar_unique"):
        supabase.auth.sign_out()
        if "user" in st.session_state: del st.session_state.user
        st.rerun()
    st.divider()
    st.subheader("💰 給料設定")
    new_h = st.number_input("時給", value=settings['hourly_wage'], step=10, key="w_in")
    new_f = st.number_input("固定給", value=settings['fixed_salary'], step=1000, key="f_in")
    if st.button("設定を保存", key="save_settings"):
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
                s_iso = JST.localize(datetime.combine(d, s_t)).isoformat()
                e_iso = JST.localize(datetime.combine(d, e_t)).isoformat()
                supabase.table("todos").insert({"user_id": user_id, "title": title, "category": cat, "start_at": s_iso, "end_at": e_iso, "reminder_at": calculate_reminder(d, cat), "is_complete": False}).execute()
                st.rerun()

# --- 9. メイン画面 ---
st.markdown(f"<h1 class='main-title'>{APP_NAME}</h1>", unsafe_allow_html=True)
v_sal, f_sal, hrs = get_salary_info(current_todos, settings['hourly_wage'], settings['fixed_salary'])

col_sal, col_rem = st.columns([1, 2])
with col_sal:
    st.markdown(f"""<div class="salary-box"><p style='margin:0; font-size:0.9em; color:#666;'>💰 今月の見込み合計</p><h2 style='margin:0; color:#9B59B6;'>¥{v_sal + f_sal:,}</h2><div class="salary-detail">内訳: 固定 ¥{f_sal:,} + 時給分 ¥{v_sal:,}<br>(バイト合計: {hrs} 時間)</div></div>""", unsafe_allow_html=True)

with col_rem:
    upcoming = [r for r in current_todos if r.get('reminder_at') and not r.get('is_complete', False)]
    if upcoming:
        today = datetime.now(JST).strftime('%Y-%m-%d')
        future = [r for r in upcoming if r['reminder_at'] <= today]
        if future:
            r = sorted(future, key=lambda x: x['reminder_at'])[0]
            st.warning(f"🔔 リマインド: {r['title']} (期限間近です)")

events = []
colors = {"テスト": "#FF4B4B", "課題": "#FFA421", "日用品": "#7792E3", "遊び": "#21C354", "バイト": "#9B59B6", "その他": "#A3A8B4"}
for item in current_todos:
    done = item.get('is_complete', False)
    events.append({"id": str(item['id']), "title": f"{'✅' if done else ''}[{item['category']}] {item['title']}", "start": datetime.fromisoformat(item['start_at']).astimezone(JST).replace(tzinfo=None).isoformat(), "end": datetime.fromisoformat(item['end_at']).astimezone(JST).replace(tzinfo=None).isoformat(), "backgroundColor": "#bdc3c7" if done else colors.get(item['category'], "#3D3333"), "allDay": False})

cal_options = {"headerToolbar": {"left": "today prev,next", "center": "title", "right": "dayGridMonth,timeGridWeek,timeGridDay"}, "initialView": "dayGridMonth", "locale": "ja", "slotMinTime": "00:00:00", "slotMaxTime": "24:00:00", "editable": True, "eventDisplay": "block"}
state = calendar(events=events, options=cal_options, key="manetime_final_stable_v3")

if state.get("eventClick"): show_event_details(state["eventClick"]["event"]["id"])
if state.get("eventChange"):
    eid = state["eventChange"]["event"]["id"]
    new_s = datetime.fromisoformat(state["eventChange"]["event"]["start"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    new_e = datetime.fromisoformat(state["eventChange"]["event"]["end"].replace('Z', '+00:00')).astimezone(JST).isoformat()
    supabase.table("todos").update({"start_at": new_s, "end_at": new_e}).eq("id", eid).execute()
    st.rerun()
