import os
import sys
import sqlite3
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from collections import namedtuple
import pandas as pd
import eel

# Функция для корректного определения путей в скомпилированном приложении
def resource_path(relative_path):
    """Получает абсолютный путь для работы в dev и после компиляции"""
    try:
        # PyInstaller создает временную папку в _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Инициализация Eel с правильными путями
eel.init(resource_path('web'))

def get_db_path():
    """Возвращает правильный путь к базе данных в зависимости от режима работы"""
    if getattr(sys, 'frozen', False):
        # Если приложение скомпилировано, используем папку с исполняемым файлом
        application_path = os.path.dirname(sys.executable)
    else:
        # В режиме разработки используем текущую папку
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    return os.path.join(application_path, 'bets.db')

def check_and_create_db():
    """Проверяет наличие БД и создает новую при необходимости"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"База данных не найдена, создаем новую: {db_path}")
        init_db()
    else:
        print(f"Используем существующую базу данных: {db_path}")

# Подключение к базе данных
def get_db_connection():
    """Создает соединение с базой данных"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация базы данных
def init_db():
    """Создает таблицу ставок, если она не существует"""
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
    
    # Можно добавить тестовые данные при первом запуске
    cursor.execute('''
        INSERT INTO bets (home_team, away_team, index_val, coefficient, bet_amount, date, result)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        'Команда А', 'Команда Б', 1.5, 2.0, 1000, '2023-01-01', 'win'
    ))
    
    conn.commit()
    conn.close()

# Структура для статистики
Stats = namedtuple('Stats', [
    'total_profit', 'pass_rate', 'won_bets', 'returned_bets',
    'total_bets', 'max_drawdown', 'roi', 'avg_coefficient',
    'win_streak', 'loss_streak'
])

@eel.expose
def calculate_stats():
    """Вычисление статистики по ставкам и возврат данных для отображения"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Получаем все ставки, отсортированные по дате
    cursor.execute('SELECT * FROM bets ORDER BY date ASC')
    bets = cursor.fetchall()
    total_bets = len(bets)
    won_bets = len([b for b in bets if b['result'] == 'win'])
    returned_bets = len([b for b in bets if b['result'] == 'return'])
    
    # Расчет прибыли
    profit = sum(
        b['bet_amount'] * (b['coefficient'] - 1) if b['result'] == 'win' else
        -b['bet_amount'] if b['result'] == 'loss' else 0
        for b in bets
    )
    
    # Расчет процента проходимости
    pass_rate = (won_bets / (total_bets - returned_bets)) * 100 if (total_bets - returned_bets) > 0 else 0
    
    # ROI (Return on Investment)
    total_invested = sum(b['bet_amount'] for b in bets if b['result'] != 'return')
    roi = (profit / total_invested) * 100 if total_invested > 0 else 0
    
    # Средний коэффициент
    avg_coefficient = sum(b['coefficient'] for b in bets) / total_bets if total_bets > 0 else 0
    
    # Расчет максимальной просадки
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
    
    # Расчет серий побед/поражений
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
    
    # История баланса для графика
    balance_history = []
    current_balance = 0
    for b in bets:
        if b['result'] == 'win':
            current_balance += b['bet_amount'] * (b['coefficient'] - 1)
        elif b['result'] == 'loss':
            current_balance -= b['bet_amount']
        balance_history.append((b['date'], current_balance))
    
    conn.close()
    
    # Генерация графика
    chart_url = generate_chart(balance_history) if balance_history else None
    
    # Подготовка данных для отправки в JavaScript
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
    
    # Получаем последние ставки для таблицы
    bets_for_table = get_bets_for_table()
    
    return {
        'stats': stats_dict,
        'chart_url': chart_url,
        'bets': bets_for_table
    }

def generate_chart(balance_history):
    """Генерация графика баланса в формате base64"""
    if not balance_history:
        return None
    
    dates = [datetime.strptime(item[0], '%Y-%m-%d') for item in balance_history]
    balances = [item[1] for item in balance_history]
    
    # Настройка стиля графика
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e1e')
    ax.set_facecolor('#1e1e1e')
    
    # Разделение на сегменты роста/падения
    segments = []
    current_segment = [0]
    
    for i in range(1, len(balances)):
        if (balances[i] >= balances[i-1] and balances[i-1] >= (segments[-1][-1] if segments else balances[0])) or \
           (balances[i] < balances[i-1] and balances[i-1] < (segments[-1][-1] if segments else balances[0])):
            current_segment.append(i)
        else:
            segments.append(current_segment)
            current_segment = [i-1, i]
    
    if current_segment:
        segments.append(current_segment)
    
    # Отрисовка сегментов
    for segment in segments:
        if len(segment) < 2:
            continue
            
        segment_dates = [dates[i] for i in segment]
        segment_balances = [balances[i] for i in segment]
        
        if segment_balances[-1] >= segment_balances[0]:
            ax.plot(segment_dates, segment_balances, 
                   marker='o', 
                   color='#6495ED', 
                   markersize=5, 
                   linewidth=2)
        else:
            ax.plot(segment_dates, segment_balances, 
                   marker='o', 
                   color='#f44336', 
                   markersize=5, 
                   linewidth=2)
    
    # Настройка внешнего вида
    ax.grid(True, color='#333', linestyle='--', alpha=0.5)
    ax.spines['bottom'].set_color('#333')
    ax.spines['top'].set_color('#333') 
    ax.spines['right'].set_color('#333')
    ax.spines['left'].set_color('#333')
    ax.tick_params(axis='y', colors='#e0e0e0')
    
    plt.tight_layout()
    
    # Сохранение в base64
    img = io.BytesIO()
    plt.savefig(img, format='png', facecolor='#1e1e1e', bbox_inches='tight')
    img.seek(0)
    plt.close(fig)
    
    return base64.b64encode(img.getvalue()).decode('utf-8')

def get_bets_for_table():
    """Получает ставки для отображения в таблице"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM bets ORDER BY date DESC')
    bets = cursor.fetchall()
    
    # Преобразуем в список словарей для удобства работы с JavaScript
    bets_list = []
    for bet in bets:
        bet_dict = dict(bet)
        # Преобразуем дату в формат дд.мм.гг
        bet_date = datetime.strptime(bet_dict['date'], '%Y-%m-%d')
        bet_dict['formatted_date'] = bet_date.strftime('%d.%m.%y')
        bets_list.append(bet_dict)
    
    conn.close()
    return bets_list

@eel.expose
def add_bet(bet_data):
    """Добавление новой ставки в базу данных"""
    try:
        date_str = bet_data['date'].replace(',', '.')
        day, month, year = map(int, date_str.split('.'))
        date = f"{year}-{month:02d}-{day:02d}"  # Формат YYYY-MM-DD
        
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
    """Удаление ставки по ID"""
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
    """Экспорт данных в Excel файл"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM bets ORDER BY date ASC')
        bets = cursor.fetchall()
        
        # Преобразуем данные в DataFrame
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
        
        # Создаем Excel файл в памяти
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Ставки', index=False)
        
        output.seek(0)
        excel_data = output.getvalue()
        
        # Конвертируем в base64 для передачи в JavaScript
        excel_base64 = base64.b64encode(excel_data).decode('utf-8')
        
        conn.close()
        return {'success': True, 'data': excel_base64, 'filename': 'bet_history.xlsx'}
    except Exception as e:
        print(f"Ошибка при экспорте в Excel: {e}")
        return {'success': False, 'message': f'Ошибка при экспорте: {str(e)}'}

@eel.expose
def import_from_excel(excel_data):
    """Импорт данных из Excel файла"""
    try:
        # Декодируем base64
        excel_bytes = base64.b64decode(excel_data.split(',')[1])
        
        # Читаем Excel файл
        df = pd.read_excel(io.BytesIO(excel_bytes))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Очищаем существующие данные
        cursor.execute('DELETE FROM bets')
        conn.commit()
        
        # Добавляем новые данные
        for _, row in df.iterrows():
            try:
                date_str = str(row['Дата']).replace(',', '.')
                if '-' in date_str:
                    # Дата в формате YYYY-MM-DD
                    date = date_str
                else:
                    # Дата в формате DD.MM.YYYY
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

if __name__ == '__main__':
    # Проверяем и создаем БД при необходимости
    check_and_create_db()
    
    # Запуск приложения
    print("Запуск приложения...")
    eel.start('index.html', 
              size=(1200, 800),
              mode='default',
              suppress_error=True,
              port=0,  # Автоматический выбор порта
              close_callback=lambda: os._exit(0))  # Корректное завершение