import gspread
import uuid
from datetime import datetime
import streamlit as st
import json

# --- НАСТРОЙКА СВЯЗИ (С КЭШИРОВАНИЕМ ПОДКЛЮЧЕНИЯ) ---
# Эта команда говорит: установи связь 1 раз и держи её открытой
@st.cache_resource
def get_connection():
    try:
        credentials_dict = json.loads(st.secrets["google_key"])
        gc = gspread.service_account_from_dict(credentials_dict)
    except Exception:
        gc = gspread.service_account(filename='credentials.json')

    return gc.open_by_url('https://docs.google.com/spreadsheets/d/1D_HdduxF55bPyvisoz9GTpeYssozQ1WnBe2nsN3KhaQ/edit')

# Получаем наше подключение из кэша
sh = get_connection()

# --- ПРОВЕРКА ПРАВ ДОСТУПА ПО ССЫЛКЕ ---
admin_param = st.query_params.get("admin")
is_admin_desktop = admin_param == "1" # Компьютерная админка
is_admin_mobile = admin_param == "2"  # Телефонная админка
is_admin = is_admin_desktop or is_admin_mobile # Любой из админов (для показа кнопок)

@st.cache_data
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
    return total  # Возвращаем честную сумму, маскировка больше не нужна

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

# Обновленная функция записи с защитой от переполнения (100) и ухода в минус (0)
def add_transaction(child_name, points_change, comment, current_balance):
    
    # ЛОГИКА ОГРАНИЧЕНИЯ ДО 100 (Начисление)
    if points_change > 0: 
        if current_balance + points_change > 100:
            # Высчитываем, сколько реально можно добавить до сотни
            points_change = 100 - current_balance 
            
    # НОВАЯ ЛОГИКА ОГРАНИЧЕНИЯ ДО 0 (Списание)
    elif points_change < 0:
        if current_balance + points_change < 0:
            # Списываем ровно столько, сколько осталось на балансе
            points_change = -current_balance
            
    # Если добавлять или списывать больше нечего (уже 100 или уже 0) — отменяем операцию
    if points_change == 0:
        return

    ws_points = sh.worksheet('История баллов')
    new_id = str(uuid.uuid4())[:8]
    current_date = datetime.now().strftime("%d.%m.%Y")
    new_row = [new_id, current_date, child_name, points_change, comment]
    ws_points.append_row(new_row)
    
    # ВАЖНО: Сбрасываем кэш, так как мы изменили таблицу!
    st.cache_data.clear()

def add_money_transaction(child_name, amount, comment):
    ws_money = sh.worksheet('История денег')
    new_id = str(uuid.uuid4())[:8]
    current_date = datetime.now().strftime("%d.%m.%Y")
    new_row = [new_id, current_date, child_name, amount, comment]
    ws_money.append_row(new_row)
    
    # ВАЖНО: Сбрасываем кэш после изменения денег
    st.cache_data.clear()

# --- НОВАЯ ЛОГИКА НАГРАД И ЦВЕТОВ ---
def get_reward_and_color(balance):
    if balance < 25:
        return "НИЧЕГО", "#800000"  # Бордовый
    elif balance < 50:
        return "СЛАДОСТИ", "#FF8C00"  # Оранжевый
    elif balance < 75:
        return "МУЛЬТИКИ", "#FFD700"  # Желтый
    else:
        return "ЭКРАН", "#32CD32"  # Зеленый

# --- ОБНОВЛЕННАЯ КАРТОЧКА РЕБЕНКА С ИНДИВИДУАЛЬНЫМ МОБИЛЬНЫМ UX ---
def draw_child_card(name, points, money, theme_color):
    reward, bar_color = get_reward_and_color(points)
    height_pct = max(0, min(points, 100)) 
    
    if is_admin_mobile:
        # 📱 МОБИЛЬНАЯ АДМИНКА (?admin=2) — Все элементы ЖЕСТКО в одну строку
        # Обязательно без пустых строк внутри кавычек, чтобы Markdown не ломал код!
        # 📱 МОБИЛЬНАЯ АДМИНКА — Ограничили ширину всей строки до 260px и отцентрировали
        html_mobile_row = f"""
<div style="display: flex; flex-direction: row; align-items: center; justify-content: space-between; gap: 8px; max-width: 260px; margin: 0 auto 5px auto;">
    <div style="font-size: 20px; font-weight: bold; color: {theme_color}; min-width: 55px; text-align: left;">{name}</div>
    <div style="flex-grow: 1; position: relative; height: 26px; border: 2px solid black; background-color: #f0f0f0; border-radius: 6px; overflow: hidden;">
        <div style="width: {height_pct}%; height: 100%; background-color: {bar_color}; transition: width 0.5s;"></div>
        <div style="position: absolute; width: 100%; top: 50%; transform: translateY(-50%); text-align: center; font-family: sans-serif; font-size: 15px; font-weight: bold; color: black; text-shadow: 1px 1px 0px white, -1px -1px 0px white, 1px -1px 0px white, -1px 1px 0px white;">
            {points}
        </div>
    </div>
    <div style="width: 75px; height: 75px; display: flex; align-items: center; justify-content: center;">
        <svg width="75" height="75" viewBox="0 0 120 100">
            <circle cx="60" cy="18" r="10" fill="#FFD700" stroke="#DAA520" stroke-width="2"/>
            <text x="60" y="21.5" font-family="sans-serif" font-size="10" font-weight="bold" fill="#DAA520" text-anchor="middle">₪</text>
            <rect x="35" y="70" width="12" height="15" rx="3" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
            <rect x="75" y="70" width="12" height="15" rx="3" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
            <polygon points="35,40 45,20 55,35" fill="#fbcfe8" stroke="#db2777" stroke-width="2" stroke-linejoin="round"/>
            <ellipse cx="60" cy="55" rx="45" ry="28" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
            <ellipse cx="105" cy="55" rx="8" ry="14" fill="#f472b6" stroke="#db2777" stroke-width="2"/>
            <circle cx="85" cy="45" r="3.5" fill="#db2777"/>
            <line x1="45" y1="35" x2="75" y2="35" stroke="#db2777" stroke-width="3" stroke-linecap="round"/>
            <text x="60" y="63" font-family="sans-serif" font-size="22" font-weight="bold" fill="#831843" text-anchor="middle">{money} ₪</text>
        </svg>
    </div>
</div>
"""
        st.markdown(html_mobile_row, unsafe_allow_html=True)
        
    else:
        # 💻 ДЕСКТОПНАЯ ВЕРСИЯ (ДЕТИ ИЛИ ?admin=1) — Классический крупный дашборд
        st.markdown(f"<h3 style='text-align: center; color: {theme_color}; margin-bottom: 0;'>{name}</h3>", unsafe_allow_html=True)
        
        col_bar, col_pig = st.columns(2)
        with col_bar:
            html_bar = f"""
            <div style="display: flex; justify-content: center; margin-top: 10px;">
                <div style="position: relative; height: 160px; width: 60px; border: 3px solid black; background-color: #f0f0f0; border-radius: 8px; overflow: hidden;">
                    <div style="position: absolute; bottom: 0; width: 100%; height: {height_pct}%; background-color: {bar_color}; transition: height 0.5s;"></div>
                    <div style="position: absolute; width: 100%; top: 50%; transform: translateY(-50%); text-align: center; font-family: sans-serif; font-size: 24px; font-weight: bold; color: black; text-shadow: 1px 1px 0px white, -1px -1px 0px white, 1px -1px 0px white, -1px 1px 0px white;">
                        {points}
                    </div>
                </div>
            </div>
            """
            st.markdown(html_bar, unsafe_allow_html=True)
            
        with col_pig:
            html_piggy = f"""
            <div style="display: flex; justify-content: center; align-items: center; height: 220px;">
                <svg width="210" height="210" viewBox="0 0 120 100">
                    <circle cx="60" cy="18" r="10" fill="#FFD700" stroke="#DAA520" stroke-width="2"/>
                    <text x="60" y="21.5" font-family="sans-serif" font-size="10" font-weight="bold" fill="#DAA520" text-anchor="middle">₪</text>
                    <rect x="35" y="70" width="12" height="15" rx="3" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
                    <rect x="75" y="70" width="12" height="15" rx="3" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
                    <polygon points="35,40 45,20 55,35" fill="#fbcfe8" stroke="#db2777" stroke-width="2" stroke-linejoin="round"/>
                    <ellipse cx="60" cy="55" rx="45" ry="28" fill="#fbcfe8" stroke="#db2777" stroke-width="2"/>
                    <ellipse cx="105" cy="55" rx="8" ry="14" fill="#f472b6" stroke="#db2777" stroke-width="2"/>
                    <circle cx="85" cy="45" r="3.5" fill="#db2777"/>
                    <line x1="45" y1="35" x2="75" y2="35" stroke="#db2777" stroke-width="3" stroke-linecap="round"/>
                    <text x="60" y="63" font-family="sans-serif" font-size="22" font-weight="bold" fill="#831843" text-anchor="middle">{money} ₪</text>
                </svg>
            </div>
            """
            st.markdown(html_piggy, unsafe_allow_html=True)

    # 3. Пульт управления (Для ЛЮБОГО админа)
    if is_admin:
        if is_admin_mobile:
            form_style = "max-width: 260px !important; margin: 5px auto 0 auto !important;"
        else:
            form_style = "margin-top: 10px !important;"
            
        st.markdown(f"""
            <style>
            div[data-testid="stForm"]:has(#{name}_form_marker) {{
                border: 2px solid {theme_color} !important;
                background-color: {theme_color}15 !important;
                border-radius: 14px !important;
                {form_style}
            }}
            </style>
        """, unsafe_allow_html=True)
        
        with st.form(key=f"{name}_admin_panel", clear_on_submit=True):
            st.markdown(f'<div id="{name}_form_marker" style="display:none;"></div>', unsafe_allow_html=True)
            
            st.caption("Баллы:")
            r1_col1, r1_col2 = st.columns(2)
            if r1_col1.form_submit_button("+5", use_container_width=True):
                add_transaction(name, 5, 'Начисление', points)
                st.rerun()
            if r1_col2.form_submit_button("+1", use_container_width=True):
                add_transaction(name, 1, 'Начисление', points)
                st.rerun()
                
            r2_col1, r2_col2 = st.columns(2)
            if r2_col1.form_submit_button("-1", use_container_width=True):
                add_transaction(name, -1, 'Списание', points)
                st.rerun()
            if r2_col2.form_submit_button("-5", use_container_width=True):
                add_transaction(name, -5, 'Списание', points)
                st.rerun()
                
            st.caption("Деньги:")
            amt = st.number_input("Сумма:", min_value=1, step=1, label_visibility="collapsed")
            
            c_plus, c_minus = st.columns(2)
            add_btn = c_plus.form_submit_button("➕ Плюс", use_container_width=True)
            sub_btn = c_minus.form_submit_button("➖ Минус", use_container_width=True)
            
            if add_btn:
                add_money_transaction(name, amt, "Пополнение")
                st.rerun()
            if sub_btn:
                add_money_transaction(name, -amt, "Трата")
                st.rerun()
# --- ГЛАВНЫЙ ЭКРАН ---
st.title("Kids Tracker 🚀")

if not is_admin:
    st.info("Режим просмотра")

# Загружаем данные
children_data, points_data, money_data = load_data()

# --- АДАПТИВНЫЙ ГЛАВНЫЙ ЭКРАН ---
st.divider()

# РАЗДЕЛЯЕМ ИНТЕРФЕЙСЫ
if is_admin_mobile:
    # 📱 МОБИЛЬНАЯ АДМИНКА (?admin=2) — Вкладки
    tab_k, tab_s, tab_l = st.tabs(["👦 Кир", "👧 Софа", "🦊 Лиса"])
    
    with tab_k:
        draw_child_card("Кир", calculate_balance('Кир', points_data), calculate_money('Кир', money_data), "#00BFFF")
    with tab_s:
        draw_child_card("Софа", calculate_balance('Софа', points_data), calculate_money('Софа', money_data), "#FF0000")
    with tab_l:
        draw_child_card("Лиса", calculate_balance('Лиса', points_data), calculate_money('Лиса', money_data), "#7F00FF")

else:
    # 💻 ДЕСКТОПНАЯ АДМИНКА (?admin=1) ИЛИ РЕЖИМ ДЕТЕЙ — Три колонки
    col_k, col_s, col_l = st.columns(3)
    
    with col_k:
        draw_child_card("Кир", calculate_balance('Кир', points_data), calculate_money('Кир', money_data), "#00BFFF")
    with col_s:
        draw_child_card("Софа", calculate_balance('Софа', points_data), calculate_money('Софа', money_data), "#FF0000")
    with col_l:
        draw_child_card("Лиса", calculate_balance('Лиса', points_data), calculate_money('Лиса', money_data), "#FF69B4")

# --- ЛЕГЕНДА НАГРАД (ВНИЗУ) — ТОЛЬКО ДЛЯ ДЕТЕЙ ---
if not is_admin:
    st.divider()
    legend_html = """
    <div style="display:flex; text-align:center; font-weight:bold; border: 3px solid black; margin-top: 20px;">
        <div style="flex:1; background-color:#800000; color:white; padding:15px;">0-24<br>НИЧЕГО</div>
        <div style="flex:1; background-color:#FF8C00; color:black; padding:15px; border-left:3px solid black;">25-49<br>СЛАДОСТИ</div>
        <div style="flex:1; background-color:#FFD700; color:black; padding:15px; border-left:3px solid black;">50-74<br>МУЛЬТФИЛЬМЫ</div>
        <div style="flex:1; background-color:#32CD32; color:black; padding:15px; border-left:3px solid black;">75-100<br>ЭКРАН ПО ВЫБОРУ</div>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)
