import gspread
import uuid
from datetime import datetime
import streamlit as st
import json

# --- НАСТРОЙКА СВЯЗИ ---
try:
    credentials_dict = json.loads(st.secrets["google_key"])
    gc = gspread.service_account_from_dict(credentials_dict)
except Exception:
    gc = gspread.service_account(filename='credentials.json')

sh = gc.open_by_url('https://docs.google.com/spreadsheets/d/1D_HdduxF55bPyvisoz9GTpeYssozQ1WnBe2nsN3KhaQ/edit')

# --- ПРОВЕРКА ПРАВ ДОСТУПА ПО ССЫЛКЕ ---
# Смотрим, есть ли в адресной строке ?admin=1
is_admin = st.query_params.get("admin") == "1"


# --- ФУНКЦИИ БЭКЕНДА ---
def load_data():
    ws_children = sh.worksheet('Children')
    ws_points = sh.worksheet('История баллов')
    ws_money = sh.worksheet('История денег')
    return ws_children.get_all_records(), ws_points.get_all_records(), ws_money.get_all_records()

def calculate_balance(target_name, points_data):
    total = 0
    for row in points_data:
        if row['Ребенок'] == target_name:
            total = total + int(row['Изменение баллов'])
    
    # ОГРАНИЧЕНИЕ: Если сумма больше 100, возвращаем 100
    return min(total, 100)

def calculate_money(target_name, money_data):
    total = 0
    for row in money_data:
        if row['Ребенок'] == target_name:
            total = total + int(row['Сумма'])
    return total

def get_status(balance):
    if balance >= 100:
        return "👑 Супер-герой"
    elif balance >= 50:
        return "⭐ Отличный прогресс"
    else:
        return "🌱 В начале пути"

def add_transaction(child_name, points_change, comment):
    ws_points = sh.worksheet('История баллов')
    new_id = str(uuid.uuid4())[:8]
    current_date = datetime.now().strftime("%d.%m.%Y")
    new_row = [new_id, current_date, child_name, points_change, comment]
    ws_points.append_row(new_row)

def add_money_transaction(child_name, amount, comment):
    ws_money = sh.worksheet('История денег')
    new_id = str(uuid.uuid4())[:8]
    current_date = datetime.now().strftime("%d.%m.%Y")
    new_row = [new_id, current_date, child_name, amount, comment]
    ws_money.append_row(new_row)

def draw_child_card(name, balance):
    st.subheader(name)
    st.metric(label="Баланс", value=f"{balance} баллов", delta=get_status(balance), delta_color="normal")
    
    # Шкала прогресса (защищаем от ухода в минус)
    prog_val = max(0, balance)
    st.progress(prog_val)
    
    # ПОКАЗЫВАЕМ КНОПКИ ТОЛЬКО ЕСЛИ ЭТО АДМИН
    if is_admin:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("+5", key=f"{name}_plus5"):
                add_transaction(name, 5, 'Быстрое начисление')
                st.rerun()
        with col2:
            if st.button("+1", key=f"{name}_plus1"):
                add_transaction(name, 1, 'Быстрое начисление')
                st.rerun()
        with col3:
            if st.button("-1", key=f"{name}_minus1"):
                add_transaction(name, -1, 'Списание')
                st.rerun()
        with col4:
            if st.button("-5", key=f"{name}_minus5"):
                add_transaction(name, -5, 'Списание')
                st.rerun()
    st.divider()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("Kids Tracker 🚀")

# Если человек зашел не по секретной ссылке, покажем ему деликатное сообщение
if not is_admin:
    st.info("Режим просмотра")

if is_admin:
    st.info("Родительский режим")

children, points, money = load_data()
tab_points, tab_money = st.tabs(["🎯 Баллы", "💰 Кошельки"])

with tab_points:
    draw_child_card("Кир", calculate_balance('Кир', points))
    draw_child_card("Софа", calculate_balance('Софа', points))
    draw_child_card("Лиса", calculate_balance('Лиса', points))

with tab_money:
    st.subheader("Состояние копилок")
    col_k, col_s, col_l = st.columns(3)
    col_k.metric("Кир", f"{calculate_money('Кир', money)} ₪")
    col_s.metric("Софа", f"{calculate_money('Софа', money)} ₪")
    col_l.metric("Лиса", f"{calculate_money('Лиса', money)} ₪")
    
    st.divider()
    
    # ПОКАЗЫВАЕМ ФОРМУ ДЕНЕГ ТОЛЬКО ЕСЛИ ЭТО АДМИН
    if is_admin:
        st.subheader("Внести операцию")
        with st.form("money_form", clear_on_submit=True):
            selected_child = st.selectbox("Кому:", ["Кир", "Софа", "Лиса"])
            amount = st.number_input("Сумма (с минусом для траты):", step=1)
            comment = st.text_input("Комментарий (на что потратили/за что получили):")
            submitted = st.form_submit_button("Записать в историю")
            
            if submitted:
                if amount == 0:
                    st.error("Сумма не может быть нулевой!")
                else:
                    add_money_transaction(selected_child, amount, comment)
                    st.success("Успешно добавлено!")
                    st.rerun()