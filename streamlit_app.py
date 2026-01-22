import streamlit as st
from supabase import create_client

# --- 接続設定 ---
url = "あなたのProject URL"
key = "あなたのAPI Key"
supabase = create_client(url, key)

st.set_page_config(page_title="Supabase Todo", layout="centered")
st.title("✅ Supabase Todoリスト")

# --- 1. 新しいタスクの追加 ---
with st.form("add_task_form", clear_on_submit=True):
    new_task = st.text_input("何をする？", placeholder="例：牛乳を買う")
    submitted = st.form_submit_button("追加")
    
    if submitted and new_task:
        # データベースに書き込み
        supabase.table("todos").insert({"task": new_task}).execute()
        st.success(f"追加しました: {new_task}")

# --- 2. タスク一覧の表示と操作 ---
st.divider()
st.subheader("現在のタスク")

# データベースから最新データを取得
response = supabase.table("todos").select("*").order("inserted_at").execute()
todos = response.data

for todo in todos:
    col1, col2 = st.columns([0.8, 0.2])
    
    # タスク名の表示（完了済みなら打ち消し線）
    task_text = f"~~{todo['task']}~~" if todo['is_complete'] else todo['task']
    col1.write(task_text)
    
    # 完了/未完了の切り替えボタン
    btn_label = "戻す" if todo['is_complete'] else "完了"
    if col2.button(btn_label, key=todo['id']):
        supabase.table("todos").update({"is_complete": not todo['is_complete']}).eq("id", todo['id']).execute()
        st.rerun() # 画面を更新
