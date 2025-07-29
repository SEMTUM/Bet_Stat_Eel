import os
import sys
import sqlite3
import atexit
import psutil
from datetime import datetime, timedelta
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from collections import namedtuple
import pandas as pd
import eel
import random
from matplotlib.ticker import MaxNLocator

def kill_child_processes():
    try:
        current_process = psutil.Process()
        for child in current_process.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception as e:
        print(f"Ошибка при завершении процессов: {e}")

atexit.register(kill_child_processes)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

eel.init(resource_path('web'))

def get_db_path():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, 'bets.db')

def check_and_create_db():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"База данных не найдена, создаем новую: {db_path}")
        init_db()

def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            coefficient REAL NOT NULL,
            bet_amount REAL NOT NULL,
            date DATE NOT NULL,
            result TEXT NOT NULL,
            source TEXT DEFAULT 'Не указан'
        )
    ''')
    conn.commit()
    conn.close()

Stats = namedtuple('Stats', [
    'total_profit', 'pass_rate', 'won_bets', 'returned_bets',
    'total_bets', 'max_drawdown', 'roi', 'avg_coefficient',
    'win_streak', 'loss_streak'
])

@eel.expose
def get_sources():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT source FROM bets WHERE source IS NOT NULL AND source != 'Не указан'")
    sources = [row['source'] for row in cursor.fetchall()]
    conn.close()
    return sources

@eel.expose
def get_available_months():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT strftime('%m', date) as month FROM bets ORDER BY month DESC")
    months = [row['month'] for row in cursor.fetchall()]
    conn.close()
    return months

def get_source_balance_history(source):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT date, result, coefficient, bet_amount 
        FROM bets 
        WHERE source = ? AND result != 'pending'
        ORDER BY date ASC
    '''
    cursor.execute(query, (source,))
    bets = cursor.fetchall()
    
    daily_balances = {}
    current_balance = 0
    
    for bet in bets:
        bet_date = datetime.strptime(bet['date'], '%Y-%m-%d').date()
        
        if bet['result'] == 'win':
            current_balance += bet['bet_amount'] * (bet['coefficient'] - 1)
        elif bet['result'] == 'loss':
            current_balance -= bet['bet_amount']
        
        daily_balances[bet_date] = current_balance
    
    conn.close()
    return sorted([(date.strftime('%Y-%m-%d'), balance) for date, balance in daily_balances.items()], key=lambda x: x[0])

@eel.expose
def calculate_stats(date_filter=None, coeff_filter=None, source_filter=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM bets WHERE result != "pending"'
    params = []
    
    if date_filter and date_filter != 'all':
        month_mapping = {
            'january': '01', 'february': '02', 'march': '03',
            'april': '04', 'may': '05', 'june': '06',
            'july': '07', 'august': '08', 'september': '09',
            'october': '10', 'november': '11', 'december': '12'
        }
        month_num = month_mapping.get(date_filter.lower())
        if month_num:
            query += ' AND strftime("%m", date) = ?'
            params.append(month_num)
    
    if coeff_filter and isinstance(coeff_filter, dict):
        min_coeff = coeff_filter.get('min')
        max_coeff = coeff_filter.get('max')
        if min_coeff is not None and max_coeff is not None:
            query += ' AND coefficient BETWEEN ? AND ?'
            params.extend([min_coeff, max_coeff])
    
    if source_filter and source_filter != 'all':
        if source_filter == 'Не указан':
            query += ' AND (source IS NULL OR source = ?)'
        else:
            query += ' AND source = ?'
        params.append(source_filter)
    
    query += ' ORDER BY date ASC'
    cursor.execute(query, params)
    bets = cursor.fetchall()
    
    total_bets = len(bets)
    won_bets = len([b for b in bets if b['result'] == 'win'])
    returned_bets = len([b for b in bets if b['result'] == 'return'])
    
    profit = sum(
        b['bet_amount'] * (b['coefficient'] - 1) if b['result'] == 'win' else
        -b['bet_amount'] if b['result'] == 'loss' else 0
        for b in bets
    )
    
    pass_rate = (won_bets / (total_bets - returned_bets)) * 100 if (total_bets - returned_bets) > 0 else 0
    
    total_invested = sum(b['bet_amount'] for b in bets if b['result'] != 'return')
    roi = (profit / total_invested) * 100 if total_invested > 0 else 0
    
    avg_coefficient = sum(b['coefficient'] for b in bets) / total_bets if total_bets > 0 else 0
    
    balance = 0
    max_balance = 0
    max_drawdown = 0
    for b in bets:
        if b['result'] == 'win':
            balance += b['bet_amount'] * (b['coefficient'] - 1)
        elif b['result'] == 'loss':
            balance -= b['bet_amount']
        
        if balance > max_balance:
            max_balance = balance
        
        drawdown = max_balance - balance
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    current_streak = 0
    win_streak = 0
    loss_streak = 0
    last_result = None
    
    for b in bets:
        if b['result'] == 'win':
            current_streak = current_streak + 1 if last_result == 'win' else 1
            win_streak = max(win_streak, current_streak)
        elif b['result'] == 'loss':
            current_streak = current_streak + 1 if last_result == 'loss' else 1
            loss_streak = max(loss_streak, current_streak)
        
        last_result = b['result']
    
    balance_history = []
    daily_balances = {}
    current_date = None
    current_balance = 0
    
    for b in bets:
        bet_date = datetime.strptime(b['date'], '%Y-%m-%d').date()
        if current_date is None or bet_date != current_date:
            if current_date is not None:
                daily_balances[current_date] = current_balance
            current_date = bet_date
        
        if b['result'] == 'win':
            current_balance += b['bet_amount'] * (b['coefficient'] - 1)
        elif b['result'] == 'loss':
            current_balance -= b['bet_amount']
    
    if current_date is not None:
        daily_balances[current_date] = current_balance
    
    balance_history = sorted([(date.strftime('%Y-%m-%d'), balance) for date, balance in daily_balances.items()], key=lambda x: x[0])
    
    conn.close()
    
    chart_url = generate_chart(balance_history, date_filter, source_filter) if balance_history else None
    
    stats_dict = {
        'total_profit': profit,
        'pass_rate': pass_rate,
        'won_bets': won_bets,
        'returned_bets': returned_bets,
        'total_bets': total_bets,
        'max_drawdown': max_drawdown,
        'roi': roi,
        'avg_coefficient': avg_coefficient,
        'win_streak': win_streak,
        'loss_streak': loss_streak
    }
    
    bets_for_table = get_bets_for_table(date_filter, coeff_filter, source_filter)
    available_months = get_available_months()
    sources = get_sources()
    
    return {
        'stats': stats_dict,
        'chart_url': chart_url,
        'bets': bets_for_table,
        'sources': sources,
        'available_months': available_months
    }



##############################################################################################################



def generate_chart(balance_history, date_filter=None, source_filter=None):
    """Генерирует график баланса с историей по всем источникам ставок.
    
    Args:
        balance_history: Список кортежей (дата, баланс) для основного графика
        date_filter: Фильтр по месяцу (None или 'all' - все данные)
        source_filter: Фильтр по источнику (None или 'all' - все источники)
    
    Returns:
        Base64-encoded PNG изображение или None если нет данных
    """
    
    # Проверка наличия данных для построения графика
    if not balance_history:
        return None
    
    # Преобразование строковых дат в объекты datetime
    dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in balance_history]
    # Извлечение значений баланса
    balances = [item[1] for item in balance_history]
    
    # Установка темного стиля графика
    plt.style.use('dark_background')
    # Создание фигуры с указанным размером и цветом фона
    fig, ax = plt.subplots(figsize=(25, 12), facecolor='#1e1e1e')
    # Установка цвета фона области графика
    ax.set_facecolor('#1e1e1e')
    
    # Получение текущих координат области графика
    box = ax.get_position()
    # Уменьшение ширины графика для места под легенду
    ax.set_position([box.x0, box.y0, box.width * 0.98, box.height])
    
    # Определение первой даты
    first_date = dates[0]
    # Получение последней даты в данных (без времени)
    last_main_date = dates[-1].date()
    # Текущая дата
    today = datetime.now().date()
    # Определение правой границы графика (макс. из последней даты и сегодня)
    xlim_right = max(datetime.combine(last_main_date, datetime.min.time()), 
                    datetime.combine(today, datetime.min.time()))
    
    # Добавление нулевой точки в начало данных
    all_dates = [first_date] + dates
    all_balances = [0] + balances
    
    # Построение основной линии графика (общий баланс)
    main_line, = ax.plot(all_dates, all_balances, 
                       color="#5B8AE0",  # Синий цвет линии
                       linewidth=3.5,      # Толщина линии
                       alpha=1,        # Прозрачность
                       marker='',        # Без маркеров
                       markersize=1,     # Размер маркеров
                       markerfacecolor="#4169E194",  # Цвет заливки маркера
                       markeredgecolor='white',      # Цвет границы маркера
                       markeredgewidth=1.5,          # Толщина границы маркера
                       linestyle='-',    # Сплошная линия
                       solid_capstyle='round',  # Закругленные концы линии
                       solid_joinstyle='round', # Закругленные соединения
                       zorder=3,         # Порядок отрисовки (выше других)
                       label='Вся прибыль')  # Метка для легенды
    
    # Получение списка источников из базы данных
    sources = get_sources()
    # Получение цветовой палитры для линий источников
    source_colors = plt.cm.tab20.colors
    # Список для хранения линий источников
    source_lines = []
    
    # Построение графиков для каждого источника
    for i, source in enumerate(sources):
        # Получение истории баланса для конкретного источника
        source_history = get_source_balance_history(source)
        if not source_history:
            continue
            
        # Преобразование дат и балансов источника
        source_dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in source_history]
        source_balances = [item[1] for item in source_history]
        
        # Добавление нулевой точки и точки на правый край
        full_source_dates = [first_date] + source_dates + [xlim_right]
        full_source_balances = [0] + source_balances + [source_balances[-1] if source_balances else 0]
        
        # Построение линии для источника (пунктирная)
        line, = ax.plot(full_source_dates, full_source_balances,
                      color=source_colors[i % len(source_colors)],  # Цвет из палитры
                      linewidth=1.5,     # Толщина линии
                      alpha=1,           # Прозрачность
                      linestyle='--',    # Пунктирная линия
                      zorder=2,          # Порядок отрисовки (ниже основной)
                      label=source)      # Метка для легенды
        source_lines.append(line)
    
    # Проверка, является ли последняя дата сегодняшним днем
    is_today = last_main_date == today
    # Проверка, применен ли фильтр по месяцу
    is_month_filter = date_filter and date_filter != 'all'
    
    # Подсветка последнего отрезка (если данных больше 1 и не фильтр по месяцу или сегодня)
    if len(dates) > 1 and (not is_month_filter or is_today):
        # Выбор цвета в зависимости от направления изменения баланса
        last_color = "#4CAF50" if balances[-1] >= balances[-2] else "#f44336"
        
        # Построение выделенного отрезка
        current_line, = ax.plot([dates[-2], dates[-1]], [balances[-2], balances[-1]], 
                              color=last_color,
                              linewidth=3,
                              alpha=0.9,
                              zorder=4)  # Выше основной линии
        
        # Добавление точки на последнее значение
        ax.scatter(dates[-1], balances[-1], 
                  color=last_color,
                  s=150,         # Размер точки
                  zorder=5)      # Выше всех линий
    
    # Заливка области под графиком
    ax.fill_between(all_dates, all_balances, min(all_balances) if min(all_balances) < 0 else 0,
                   color="#4169E19E",  # Цвет заливки
                   alpha=0.05,         # Прозрачность
                   interpolate=True)   # Сглаживание
    
    # Настройка сетки
    ax.grid(True,
           color='#444',       # Цвет линий сетки
           linestyle=':',      # Точечный стиль
           alpha=0.5)          # Прозрачность
    
    # Настройка границ графика
    for spine in ['bottom', 'top', 'right', 'left']:
        ax.spines[spine].set_color('#444')  # Цвет границ
        ax.spines[spine].set_linewidth(2.0) # Толщина границ
    
    # Настройка меток осей
    ax.tick_params(axis='both',
                  colors="#999999",  # Цвет меток
                  labelsize=24)       # Размер шрифта
    # Отступы для основных и второстепенных меток
    ax.tick_params(axis='both', which='major', pad=26)
    ax.tick_params(axis='both', which='minor', pad=26)
    
    # Настройка границ графика по X
    right_padding = timedelta(hours=2)  # Отступ справа (2 часа)
    if date_filter and date_filter != 'all':
        # Для фильтра по месяцу - от первой до последней даты + отступ
        ax.set_xlim([dates[0], dates[-1] + right_padding])
    else:
        # Для общего графика - от первой даты до сегодня + отступ
        ax.set_xlim([first_date, xlim_right + right_padding])
    
    # Формат отображения дат на оси X (день.месяц)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d.%m'))
    
    # Горизонтальная линия нуля
    zero_line = ax.axhline(0,
                          color='#888',      # Цвет линии
                          linestyle='--',    # Пунктир
                          linewidth=1.5,     # Толщина
                          alpha=0.3,         # Прозрачность
                          zorder=1)          # Ниже всех
    
    # Создание и настройка легенды
    legend = ax.legend(
        loc='center left',          # Позиционирование
        bbox_to_anchor=(1.05, 0.5), # Смещение относительно графика
        frameon=True,               # Без рамки
        fontsize=26,                # Размер шрифта
        framealpha=1.0,             # Прозрачность рамки (0-1)
        edgecolor='#444',           # Цвет границы
        facecolor='#1e1e1e',      # Цвет фона
        borderpad=2.0,              # Внутренний отступ (в пунктах)
        borderaxespad=2.0)          # Отступ от границ график
        
    legend.get_frame().set_linewidth(2)              
    
    # Настройка стиля текста в легенде
    for text in legend.get_texts():
        text.set_color("#999999")     # Цвет текста
        text.set_fontsize(26)         # Размер шрифта
        text.set_fontweight('normal')  # Насыщенность
        text.set_fontstyle('normal')  # Стиль
        text.set_fontfamily('Arial')  # Шрифт
        
    
    # Сохранение графика в буфер
    img = io.BytesIO()
    plt.savefig(img, 
               format='png',          # Формат изображения
               facecolor='#1e1e1e',   # Цвет фона
               dpi=100,               # Разрешение
               bbox_inches='tight',   # Обрезка пустых областей
               transparent=False)     # Непрозрачный фон
    img.seek(0)  # Перемотка буфера в начало
    plt.close(fig)  # Закрытие фигуры
    
    # Возврат base64-encoded изображения
    return base64.b64encode(img.getvalue()).decode('utf-8')


###############################################################################################



def get_bets_for_table(date_filter=None, coeff_filter=None, source_filter=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM bets'
    params = []
    
    if date_filter and date_filter != 'all':
        month_mapping = {
            'january': '01', 'february': '02', 'march': '03',
            'april': '04', 'may': '05', 'june': '06',
            'july': '07', 'august': '08', 'september': '09',
            'october': '10', 'november': '11', 'december': '12'
        }
        month_num = month_mapping.get(date_filter.lower())
        if month_num:
            query += ' WHERE strftime("%m", date) = ?'
            params.append(month_num)
    
    if coeff_filter and isinstance(coeff_filter, dict):
        min_coeff = coeff_filter.get('min')
        max_coeff = coeff_filter.get('max')
        if min_coeff is not None and max_coeff is not None:
            if 'WHERE' not in query:
                query += ' WHERE'
            else:
                query += ' AND'
            query += ' coefficient BETWEEN ? AND ?'
            params.extend([min_coeff, max_coeff])
    
    if source_filter and source_filter != 'all':
        if 'WHERE' not in query:
            query += ' WHERE'
        else:
            query += ' AND'
        if source_filter == 'Не указан':
            query += ' (source IS NULL OR source = ?)'
        else:
            query += ' source = ?'
        params.append(source_filter)
    
    query += ' ORDER BY date DESC, id DESC'
    cursor.execute(query, params)
    bets = cursor.fetchall()
    
    bets_list = []
    for bet in bets:
        bet_dict = dict(bet)
        bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
        bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%Y')
        bet_dict['source'] = bet_dict.get('source', 'Не указан')
        bets_list.append(bet_dict)
    
    conn.close()
    return bets_list

@eel.expose
def add_bet(bet_data):
    try:
        date_str = bet_data['date'].replace(',', '.')
        day, month, year = map(int, date_str.split('.'))
        date = f"{year}-{month:02d}-{day:02d}"
        
        source = bet_data.get('source', 'Не указан')
        if not source or source == 'Выберите источник':
            source = 'Не указан'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bets (event, coefficient, bet_amount, date, result, source)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            bet_data['event'],
            float(bet_data['coefficient']),
            float(bet_data['bet_amount']),
            date,
            bet_data['result'],
            source
        ))
        
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Ставка успешно добавлена'}
    except Exception as e:
        print(f"Ошибка при добавлении ставки: {e}")
        return {'success': False, 'message': f'Ошибка при добавлении ставки: {str(e)}'}

@eel.expose
def update_bet(bet_id, bet_data):
    try:
        date_str = bet_data['date'].replace(',', '.')
        day, month, year = map(int, date_str.split('.'))
        date = f"{year}-{month:02d}-{day:02d}"
        
        source = bet_data.get('source', 'Не указан')
        if not source or source == 'Выберите источник':
            source = 'Не указан'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE bets SET 
                event = ?,
                coefficient = ?,
                bet_amount = ?,
                date = ?,
                result = ?,
                source = ?
            WHERE id = ?
        ''', (
            bet_data['event'],
            float(bet_data['coefficient']),
            float(bet_data['bet_amount']),
            date,
            bet_data['result'],
            source,
            bet_id
        ))
        
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Ставка успешно обновлена'}
    except Exception as e:
        print(f"Ошибка при обновлении ставки: {e}")
        return {'success': False, 'message': f'Ошибка при обновлении ставки: {str(e)}'}

@eel.expose
def get_bet(bet_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bets WHERE id = ?', (bet_id,))
        bet = cursor.fetchone()
        
        if bet:
            bet_dict = dict(bet)
            bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
            bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%Y')
            bet_dict['source'] = bet_dict.get('source', 'Не указан')
            conn.close()
            return {'success': True, 'bet': bet_dict}
        else:
            conn.close()
            return {'success': False, 'message': 'Ставка не найдена'}
    except Exception as e:
        print(f"Ошибка при получении ставки: {e}")
        return {'success': False, 'message': f'Ошибка при получении ставки: {str(e)}'}

@eel.expose
def delete_bet(bet_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM bets WHERE id = ?', (bet_id,))
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Ставка успешно удалена'}
    except Exception as e:
        print(f"Ошибка при удалении ставки: {e}")
        return {'success': False, 'message': f'Ошибка при удалении ставки: {str(e)}'}

@eel.expose
def export_to_excel():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bets ORDER BY date ASC')
        bets = cursor.fetchall()
        
        data = []
        for bet in bets:
            bet_dict = dict(bet)
            
            profit = 0
            if bet_dict['result'] == 'win':
                profit = bet_dict['bet_amount'] * (bet_dict['coefficient'] - 1)
            elif bet_dict['result'] == 'loss':
                profit = -bet_dict['bet_amount']
            
            result_text = {
                'win': 'WIN',
                'loss': 'LOSS',
                'return': 'Возврат',
                'pending': 'В ожидании'
            }.get(bet_dict['result'], bet_dict['result'])
            
            data.append({
                'Дата': bet_dict['date'],
                'Спортивное Событие': bet_dict['event'],
                'КЭФ': bet_dict['coefficient'],
                'Сумма': bet_dict['bet_amount'],
                'Результат': result_text,
                'Доход': profit,
                'Источник': bet_dict.get('source', 'Не указан')
            })
        
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Ставки', index=False)
        
        output.seek(0)
        excel_data = output.getvalue()
        
        excel_base64 = base64.b64encode(excel_data).decode('utf-8')
        
        conn.close()
        return {'success': True, 'data': excel_base64, 'filename': 'bet_history.xlsx'}
    except Exception as e:
        print(f"Ошибка при экспорте в Excel: {e}")
        return {'success': False, 'message': f'Ошибка при экспорте: {str(e)}'}

@eel.expose
def import_from_excel(excel_data):
    try:
        excel_bytes = base64.b64decode(excel_data.split(',')[1])
        df = pd.read_excel(io.BytesIO(excel_bytes))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM bets')
        conn.commit()
        
        for _, row in df.iterrows():
            try:
                date_str = str(row['Дата']).replace(',', '.')
                if '-' in date_str:
                    date = date_str
                else:
                    day, month, year = map(int, date_str.split('.'))
                    date = f"{year}-{month:02d}-{day:02d}"
                
                result_text = str(row['Результат']).lower()
                if result_text == 'win':
                    result_text = 'win'
                elif result_text == 'loss':
                    result_text = 'loss'
                elif result_text == 'возврат':
                    result_text = 'return'
                elif result_text == 'в ожидании':
                    result_text = 'pending'
                
                source = str(row.get('Источник', 'Не указан'))
                if not source or source.lower() == 'nan':
                    source = 'Не указан'
                
                cursor.execute('''
                    INSERT INTO bets (event, coefficient, bet_amount, date, result, source)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    str(row['Спортивное Событие']),
                    float(row['КЭФ']),
                    float(row['Сумма']),
                    date,
                    result_text,
                    source
                ))
            except Exception as e:
                print(f"Ошибка обработки строки: {e}")
                continue
        
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Данные успешно импортированы'}
    except Exception as e:
        print(f"Ошибка при импорте из Excel: {e}")
        return {'success': False, 'message': f'Ошибка при импорте: {str(e)}'}

@eel.expose
def close_app():
    kill_child_processes()
    os._exit(0)

def close_callback(route, websockets):
    close_app()

if __name__ == '__main__':
    check_and_create_db()
    
    try:
        port = random.randint(8000, 8999)
        eel.start('index.html',
                 size=(1200, 800),
                 mode='default',
                 host='localhost',
                 port=port,
                 close_callback=close_callback,
                 suppress_error=True,
                 cmdline_args=['--app', f'http://localhost:{port}'])
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
    finally:
        kill_child_processes()
        #.....