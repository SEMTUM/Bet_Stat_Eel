import os
import sys
import sqlite3
import atexit
import psutil
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from collections import namedtuple
import pandas as pd
import eel

# Функция для завершения дочерних процессов
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

# Регистрируем функцию завершения
atexit.register(kill_child_processes)

# Функция для корректного определения путей
def resource_path(relative_path):
    """Получает абсолютный путь для работы в dev и после компиляции"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Инициализация Eel с правильными путями
eel.init(resource_path('web'))

def get_db_path():
    """Возвращает правильный путь к базе данных"""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, 'bets.db')

def check_and_create_db():
    """Проверяет наличие БД и создает новую при необходимости"""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"База данных не найдена, создаем новую: {db_path}")
        init_db()

def get_db_connection():
    """Создает соединение с базой данных"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            index_val REAL NOT NULL,
            coefficient REAL NOT NULL,
            bet_amount REAL NOT NULL,
            date DATE NOT NULL,
            result TEXT NOT NULL
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
def calculate_stats():
    """Расчет статистики"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM bets ORDER BY date ASC')
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
    current_balance = 0
    for b in bets:
        if b['result'] == 'win':
            current_balance += b['bet_amount'] * (b['coefficient'] - 1)
        elif b['result'] == 'loss':
            current_balance -= b['bet_amount']
        balance_history.append((b['date'], current_balance))
    
    conn.close()
    
    chart_url = generate_chart(balance_history) if balance_history else None
    
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
    
    bets_for_table = get_bets_for_table()
    
    return {
        'stats': stats_dict,
        'chart_url': chart_url,
        'bets': bets_for_table
    }


#############################################################################



def generate_chart(balance_history):
    """Генерация графика баланса с улучшенной визуализацией"""
    if not balance_history:
        return None
    
    # Преобразование данных: даты из строк в объекты datetime и получение значений баланса
    dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in balance_history]
    balances = [item[1] for item in balance_history]
    
    # Настройка стиля и размера графика
    plt.style.use('dark_background')  # Используем темный фон для графика
    fig, ax = plt.subplots(figsize=(20, 10), facecolor='#1e1e1e')  # Создаем фигуру размером 20x10 дюймов
    ax.set_facecolor('#1e1e1e')  # Устанавливаем цвет фона области графика
    
    # Основная линия графика с плавными переходами
    line, = ax.plot(dates, balances, 
                   color="#5B8AE0",  # Цвет линии (голубой)
                   linewidth=3,  # Толщина линии (в пикселях)
                   alpha=0.9,  # Прозрачность линии (0-1)
                   marker='',  # Тип маркера (круги)
                   markersize=1,  # Размер маркеров (в пунктах)
                   markerfacecolor="#4169E194",  # Цвет заливки маркеров
                   markeredgecolor='white',  # Цвет границы маркеров
                   markeredgewidth=1.5,  # Толщина границы маркеров
                   linestyle='-',  # Стиль линии (сплошная)
                   solid_capstyle='round',  # Скругление концов линии
                   solid_joinstyle='round',  # Скругление соединений сегментов
                   zorder=3)  # Порядок отрисовки (выше других элементов)
    
    # Плавная заливка под линией с градиентом
    ax.fill_between(dates, balances, min(balances) if min(balances) < 0 else 0,
                   color="#4169E19E",  # Цвет заливки
                   alpha=0.10,  # Прозрачность заливки
                   interpolate=True)  # Сглаживание границ заливки
    
    # Улучшенная сетка
    ax.grid(True,  # Включение сетки
           color='#444',  # Цвет линий сетки
           linestyle=':',  # Стиль линий (точечный)
           alpha=0.4)  # Прозрачность сетки
    
    # Оси и рамка
    for spine in ['bottom', 'top', 'right', 'left']:
        ax.spines[spine].set_color('#666')  # Цвет границ графика
        ax.spines[spine].set_linewidth(1.5)  # Толщина границ
    
    # Подписи осей
    ax.tick_params(axis='both',  # Настройка для обеих осей
                  colors="#8D8D8D",  # Цвет подписей
                  labelsize=22)  # Размер шрифта подписей
    ax.tick_params(axis='both', which='major', pad=20)  # Основные деления
    ax.tick_params(axis='both', which='minor', pad=20)   # Второстепенные деления
    
    # Форматирование дат на оси X
    
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m.%Y'))  # Формат даты (день.месяц.год)
    
    # Нулевая линия (горизонтальная)
    zero_line = ax.axhline(0,  # Y-координата линии
                          color='#888',  # Цвет линии
                          linestyle='--',  # Стиль линии (пунктир)
                          linewidth=1.2,  # Толщина линии
                          alpha=0.7,  # Прозрачность
                          zorder=1)  # Порядок отрисовки
    
    
    # Сохранение с высоким качеством
    img = io.BytesIO()  # Создаем буфер для сохранения изображения
    plt.savefig(img, 
               format='png',  # Формат изображения
               facecolor='#1e1e1e',  # Цвет фона
               dpi=120,  # Разрешение (точек на дюйм)
               bbox_inches='tight',  # Обрезка пустых областей
               transparent=False)  # Непрозрачный фон
    img.seek(0)  # Перемещаем указатель в начало буфера
    plt.close(fig)  # Закрываем фигуру для освобождения памяти
    
    return base64.b64encode(img.getvalue()).decode('utf-8')  # Возвращаем изображение в base64


############################################################################



def get_bets_for_table():
    """Получает ставки для отображения в таблице"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM bets ORDER BY date DESC')
    bets = cursor.fetchall()
    
    bets_list = []
    for bet in bets:
        bet_dict = dict(bet)
        bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
        bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%y')
        bets_list.append(bet_dict)
    
    conn.close()
    return bets_list

@eel.expose
def add_bet(bet_data):
    """Добавление новой ставки"""
    try:
        date_str = bet_data['date'].replace(',', '.')
        day, month, year = map(int, date_str.split('.'))
        date = f"{year}-{month:02d}-{day:02d}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO bets (home_team, away_team, index_val, coefficient, bet_amount, date, result)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            bet_data['home_team'],
            bet_data['away_team'],
            float(bet_data['index_val']),
            float(bet_data['coefficient']),
            float(bet_data['bet_amount']),
            date,
            bet_data['result']
        ))
        
        conn.commit()
        conn.close()
        return {'success': True, 'message': 'Ставка успешно добавлена'}
    except Exception as e:
        print(f"Ошибка при добавлении ставки: {e}")
        return {'success': False, 'message': f'Ошибка при добавлении ставки: {str(e)}'}

@eel.expose
def delete_bet(bet_id):
    """Удаление ставки"""
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
    """Экспорт в Excel"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bets ORDER BY date ASC')
        bets = cursor.fetchall()
        
        data = []
        for bet in bets:
            profit = 0
            if bet['result'] == 'win':
                profit = bet['bet_amount'] * (bet['coefficient'] - 1)
            elif bet['result'] == 'loss':
                profit = -bet['bet_amount']
            
            data.append({
                'Дата': bet['date'],
                'Хозяева': bet['home_team'],
                'Гости': bet['away_team'],
                'Индекс': bet['index_val'],
                'Коэффициент': bet['coefficient'],
                'Сумма': bet['bet_amount'],
                'Результат': bet['result'],
                'Прибыль': profit
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
    """Импорт из Excel"""
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
                
                cursor.execute('''
                    INSERT INTO bets (home_team, away_team, index_val, coefficient, bet_amount, date, result)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    str(row['Хозяева']),
                    str(row['Гости']),
                    float(row['Индекс']),
                    float(row['Коэффициент']),
                    float(row['Сумма']),
                    date,
                    str(row['Результат']).lower()
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
    """Явное завершение приложения"""
    kill_child_processes()
    os._exit(0)

def close_callback(route, websockets):
    """Обработчик закрытия окна"""
    close_app()

if __name__ == '__main__':
    check_and_create_db()
    
    try:
        eel.start('index.html',
                 size=(1200, 800),
                 mode='default',
                 host='localhost',
                 port=8080,
                 close_callback=close_callback,
                 suppress_error=True)
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
    finally:
        kill_child_processes()