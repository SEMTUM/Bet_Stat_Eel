import os
import sys
import sqlite3
import atexit
import psutil
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
from collections import namedtuple
import pandas as pd
import eel
import random
from matplotlib.lines import Line2D

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

def calculate_balance_history(bets):
    balance_history = []
    current_balance = 0
    for bet in bets:
        if bet['result'] == 'win':
            current_balance += bet['bet_amount'] * (bet['coefficient'] - 1)
        elif bet['result'] == 'loss':
            current_balance -= bet['bet_amount']
        balance_history.append((bet['date'], current_balance))
    return balance_history

def generate_chart(main_history, sources_history):
    if not main_history:
        return None
    
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(20, 10), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    # Добавляем отступ сверху (10% от высоты графика)
    plt.subplots_adjust(top=0.9)  # Было 1.0 по умолчанию
    
    colors = {
        'main': '#5B8AE0',
        'Не указан': '#888888'
    }
    
    color_palette = plt.cm.tab20(np.linspace(0, 1, len(sources_history)))
    for i, source in enumerate(sources_history.keys()):
        if source not in colors and source != 'main':
            colors[source] = color_palette[i]
    
    main_dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in main_history]
    main_balances = [item[1] for item in main_history]
    
    ax.plot(main_dates, main_balances, 
           color=colors['main'],
           linewidth=3,
           alpha=0.9,
           zorder=5,
           label='Общий баланс')
    
    for source, history in sources_history.items():
        if not history:
            continue
            
        dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in history]
        balances = [item[1] for item in history]
        
        ax.plot(dates, balances,
               color=colors.get(source, '#666666'),
               linewidth=1.5,
               alpha=0.6,
               linestyle='--',
               zorder=3,
               label=source)
    
    ax.grid(True, color='#444', linestyle=':', alpha=0.4)
    ax.axhline(0, color='#888', linestyle='--', linewidth=1.2, alpha=0.7, zorder=1)
    
    ax.tick_params(axis='both', colors="#8D8D8D", labelsize=12)
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter('%d.%m.%Y'))
    ax.set_ylabel('Баланс', color='#d4d4d4', fontsize=12)
    
    # Переносим легенду вниз с отступом
    ax.legend(loc='upper center',
             bbox_to_anchor=(0.5, -0.1),  # Сдвигаем легенду ниже
             facecolor='#1e1e1e',
             edgecolor='#333',
             fontsize=10,
             ncol=3)  # 3 колонки для компактности
    
    img = io.BytesIO()
    plt.savefig(img, 
               format='png',
               facecolor='#1e1e1e',
               dpi=120,
               bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    
    return base64.b64encode(img.getvalue()).decode('utf-8')

@eel.expose
def calculate_stats(date_filter=None, coeff_filter=None, source_filter=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM bets WHERE result != "pending"'
    params = []
    
    if date_filter and date_filter != 'all':
        if date_filter == 'current_month':
            current_month = datetime.now().strftime('%Y-%m')
            query += ' AND strftime("%Y-%m", date) = ?'
            params.append(current_month)
        else:
            month_num = {
                'january': '01', 'february': '02', 'march': '03',
                'april': '04', 'may': '05', 'june': '06',
                'july': '07', 'august': '08', 'september': '09',
                'october': '10', 'november': '11', 'december': '12'
            }.get(date_filter.lower(), None)
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
    
    main_history = calculate_balance_history(bets)
    
    sources = get_sources()
    sources_history = {}
    
    for source in sources:
        cursor.execute('''
            SELECT date, result, bet_amount, coefficient 
            FROM bets 
            WHERE source = ? AND result != 'pending'
            ORDER BY date ASC
        ''', (source,))
        source_bets = cursor.fetchall()
        sources_history[source] = calculate_balance_history(source_bets)
    
    cursor.execute('''
        SELECT date, result, bet_amount, coefficient 
        FROM bets 
        WHERE (source IS NULL OR source = 'Не указан') AND result != 'pending'
        ORDER BY date ASC
    ''')
    unknown_bets = cursor.fetchall()
    sources_history['Не указан'] = calculate_balance_history(unknown_bets)
    
    bets_for_table = get_bets_for_table(date_filter, coeff_filter, source_filter)
    
    conn.close()
    
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
    
    chart_url = generate_chart(main_history, sources_history) if main_history else None
    
    return {
        'stats': stats_dict,
        'chart_url': chart_url,
        'bets': bets_for_table,
        'sources': get_sources()
    }

@eel.expose
def get_bets_for_table(date_filter=None, coeff_filter=None, source_filter=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM bets'
    params = []
    
    if date_filter and date_filter != 'all':
        if date_filter == 'current_month':
            current_month = datetime.now().strftime('%Y-%m')
            query += ' WHERE strftime("%Y-%m", date) = ?'
            params.append(current_month)
        else:
            month_num = {
                'january': '01', 'february': '02', 'march': '03',
                'april': '04', 'may': '05', 'june': '06',
                'july': '07', 'august': '08', 'september': '09',
                'october': '10', 'november': '11', 'december': '12'
            }.get(date_filter.lower(), None)
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