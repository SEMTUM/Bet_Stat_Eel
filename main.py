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
            event TEXT NOT NULL,
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
    
    # Фильтруем ставки, исключая те, что в ожидании
    active_bets = [b for b in bets if b['result'] != 'pending']
    total_bets = len(active_bets)
    won_bets = len([b for b in active_bets if b['result'] == 'win'])
    returned_bets = len([b for b in active_bets if b['result'] == 'return'])
    
    profit = sum(
        b['bet_amount'] * (b['coefficient'] - 1) if b['result'] == 'win' else
        -b['bet_amount'] if b['result'] == 'loss' else 0
        for b in active_bets
    )
    
    pass_rate = (won_bets / (total_bets - returned_bets)) * 100 if (total_bets - returned_bets) > 0 else 0
    
    total_invested = sum(b['bet_amount'] for b in active_bets if b['result'] != 'return')
    roi = (profit / total_invested) * 100 if total_invested > 0 else 0
    
    avg_coefficient = sum(b['coefficient'] for b in active_bets) / total_bets if total_bets > 0 else 0
    
    balance = 0
    max_balance = 0
    max_drawdown = 0
    for b in active_bets:
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
    
    for b in active_bets:
        if b['result'] == 'win':
            current_streak = current_streak + 1 if last_result == 'win' else 1
            win_streak = max(win_streak, current_streak)
        elif b['result'] == 'loss':
            current_streak = current_streak + 1 if last_result == 'loss' else 1
            loss_streak = max(loss_streak, current_streak)
        
        last_result = b['result']
    
    balance_history = []
    current_balance = 0
    for b in active_bets:
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

def generate_chart(balance_history):
    """Генерация графика баланса с улучшенной визуализацией"""
    if not balance_history:
        return None
    
    dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in balance_history]
    balances = [item[1] for item in balance_history]
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(20, 10), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    line, = ax.plot(dates, balances, 
                   color="#5B8AE0",
                   linewidth=3,
                   alpha=0.9,
                   marker='',
                   markersize=1,
                   markerfacecolor="#4169E194",
                   markeredgecolor='white',
                   markeredgewidth=1.5,
                   linestyle='-',
                   solid_capstyle='round',
                   solid_joinstyle='round',
                   zorder=3)
    
    ax.fill_between(dates, balances, min(balances) if min(balances) < 0 else 0,
                   color="#4169E19E",
                   alpha=0.10,
                   interpolate=True)
    
    ax.grid(True,
           color='#444',
           linestyle=':',
           alpha=0.4)
    
    for spine in ['bottom', 'top', 'right', 'left']:
        ax.spines[spine].set_color('#666')
        ax.spines[spine].set_linewidth(1.5)
    
    ax.tick_params(axis='both',
                  colors="#8D8D8D",
                  labelsize=22)
    ax.tick_params(axis='both', which='major', pad=20)
    ax.tick_params(axis='both', which='minor', pad=20)
    
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%m.%Y'))
    
    zero_line = ax.axhline(0,
                          color='#888',
                          linestyle='--',
                          linewidth=1.2,
                          alpha=0.7,
                          zorder=1)
    
    img = io.BytesIO()
    plt.savefig(img, 
               format='png',
               facecolor='#1e1e1e',
               dpi=120,
               bbox_inches='tight',
               transparent=False)
    img.seek(0)
    plt.close(fig)
    
    return base64.b64encode(img.getvalue()).decode('utf-8')

def get_bets_for_table():
    """Получает ставки для отображения в таблице"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Изменено: добавлена сортировка по ID для записей с одинаковой датой
    cursor.execute('SELECT * FROM bets ORDER BY date DESC, id DESC')
    bets = cursor.fetchall()
    
    bets_list = []
    for bet in bets:
        bet_dict = dict(bet)
        bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
        bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%Y')
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
            INSERT INTO bets (event, coefficient, bet_amount, date, result)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            bet_data['event'],
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
def update_bet(bet_id, bet_data):
    """Обновление существующей ставки"""
    try:
        date_str = bet_data['date'].replace(',', '.')
        day, month, year = map(int, date_str.split('.'))
        date = f"{year}-{month:02d}-{day:02d}"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE bets SET 
                event = ?,
                coefficient = ?,
                bet_amount = ?,
                date = ?,
                result = ?
            WHERE id = ?
        ''', (
            bet_data['event'],
            float(bet_data['coefficient']),
            float(bet_data['bet_amount']),
            date,
            bet_data['result'],
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
    """Получение данных ставки по ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bets WHERE id = ?', (bet_id,))
        bet = cursor.fetchone()
        
        if bet:
            bet_dict = dict(bet)
            bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
            bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%Y')
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
            
            result_text = {
                'win': 'WIN',
                'loss': 'LOSS',
                'return': 'Возврат',
                'pending': 'В ожидании'
            }.get(bet['result'], bet['result'])
            
            data.append({
                'Дата': bet['date'],
                'Спортивное Событие': bet['event'],
                'КЭФ': bet['coefficient'],
                'Сумма': bet['bet_amount'],
                'Результат': result_text,
                'Доход': profit
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
                
                result_text = str(row['Результат']).lower()
                if result_text == 'win':
                    result_text = 'win'
                elif result_text == 'loss':
                    result_text = 'loss'
                elif result_text == 'возврат':
                    result_text = 'return'
                elif result_text == 'в ожидании':
                    result_text = 'pending'
                
                cursor.execute('''
                    INSERT INTO bets (event, coefficient, bet_amount, date, result)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    str(row['Спортивное Событие']),
                    float(row['КЭФ']),
                    float(row['Сумма']),
                    date,
                    result_text
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