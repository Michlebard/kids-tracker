import gspread
import uuid
from datetime import datetime
import streamlit as st

# --- НАСТРОЙКА СВЯЗИ ---
gc = gspread.service_account(filename='credentials.json')
# Твоя прямая ссылка уже вшита
sh = gc.open_by_url('https://docs.google.com/spreadsheets/d/1D_HdduxF55bPyvisoz9GTpeYssozQ1WnBe2nsN3KhaQ/edit')

# --- ФУНКЦИИ БЭКЕНДА ---
def load_data():
    ws_children = sh.worksheet('Children')
    ws_points = sh.worksheet('История баллов')
    ws_money = sh.worksheet('История денег')
    return ws_children.get_all_records(), ws_points.get_all_records(), ws_money.get_all_records()

def calculate_balance(target_name, points_data):
    total = 0
    for row in points_data:
        # Имя столбца исправлено на "Ребенок"
        if row['Ребенок'] == target_name:
            total = total + int(row['Изменение баллов'])
    return total

# Новая функция: подсчет денег
def calculate_money(target_name, money_data):
    total = 0
    for row in money_data:
        if row['Ребенок'] == target_name:
            # ВНИМАНИЕ: Если колонка с деньгами называется не 'Сумма', исправь это слово!
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

# Новая функция: запись финансовой операции
def add_money_transaction(child_name, amount, comment):
    ws_money = sh.worksheet('История денег')
    new_id = str(uuid.uuid4())[:8]
    current_date = datetime.now().strftime("%d.%m.%Y")
    
    # ВНИМАНИЕ: Проверь, совпадает ли порядок с листом "История денег"!
    # [ID, Дата, Ребенок, Сумма, Комментарий]
    new_row = [new_id, current_date, child_name, amount, comment]
    ws_money.append_row(new_row)

def draw_child_card(name, balance):
    st.subheader(name)
    st.metric(label="Баланс", value=f"{balance} баллов", delta=get_status(balance), delta_color="normal")
    
    prog_val = max(0, min(balance, 100))
    st.progress(prog_val)
    
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
children, points, money = load_data()
tab_points, tab_money = st.tabs(["🎯 Баллы", "💰 Кошельки"])

with tab_points:
    draw_child_card("Кир", calculate_balance('Кир', points))
    draw_child_card("Софа", calculate_balance('Софа', points))
    draw_child_card("Лиса", calculate_balance('Лиса', points))

# НАПОЛНЕНИЕ ВТОРОЙ ВКЛАДКИ
with tab_money:
    # 1. Показываем текущие балансы (в одну строку через колонки)
    st.subheader("Состояние копилок")
    col_k, col_s, col_l = st.columns(3)
    col_k.metric("Кир", f"{calculate_money('Кир', money)} ₪")
    col_s.metric("Софа", f"{calculate_money('Софа', money)} ₪")
    col_l.metric("Лиса", f"{calculate_money('Лиса', money)} ₪")
    
    st.divider()
    
    # 2. Форма для ввода новых операций
    st.subheader("Внести операцию")
    
    with st.form("money_form", clear_on_submit=True):
        # Выпадающий список
        selected_child = st.selectbox("Кому:", ["Кир", "Софа", "Лиса"])
        
        # Поле для цифр (step=1 означает шаг в единицу)
        amount = st.number_input("Сумма (с минусом для траты):", step=1)
        
        # Поле для текста
        comment = st.text_input("Комментарий (на что потратили/за что получили):")
        
        # Кнопка отправки формы
        submitted = st.form_submit_button("Записать в историю")
        
        if submitted:
            if amount == 0:
                st.error("Сумма не может быть нулевой!")
            else:
                add_money_transaction(selected_child, amount, comment)
                st.success("Успешно добавлено!")
                st.rerun()