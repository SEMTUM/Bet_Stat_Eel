document.addEventListener('DOMContentLoaded', function() {
    // Функция для форматирования чисел
    function formatNumber(num, decimals = 0) {
        return num.toFixed(decimals).replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ');
    }

    // Текущая редактируемая ставка (null если добавляем новую)
    let editingBetId = null;
    // Пагинация
    let currentPage = 1;
    const betsPerPage = 50;
    let allBets = [];

    // Функция для загрузки и отображения данных
    async function loadData() {
        try {
            const data = await eel.calculate_stats()();
            updateStats(data.stats);
            updateChart(data.chart_url);
            allBets = data.bets;
            updateBetsTable();
        } catch (error) {
            console.error('Ошибка при загрузке данных:', error);
            alert('Произошла ошибка при загрузке данных. Пожалуйста, попробуйте снова.');
        }
    }

    // Обновление статистики
    function updateStats(stats) {
        const statsGrid = document.getElementById('stats-grid');
        statsGrid.innerHTML = '';
        
        const statCards = [
            {
                title: 'Прибыль',
                value: stats.total_profit,
                className: stats.total_profit >= 0 ? 'positive' : 'negative',
                format: (val) => `${val >= 0 ? '+' : ''}${formatNumber(val)}`
            },
            {
                title: 'Проходимость',
                value: stats.pass_rate,
                format: (val) => `${val.toFixed(1)}%`
            },
            {
                title: 'В-ш / П-ш / В-т',
                value: `${stats.won_bets}/${stats.total_bets - stats.won_bets - stats.returned_bets}/${stats.returned_bets}`,
                className: 'text-center',
                html: `<span class="positive">${stats.won_bets}</span> / 
                       <span class="negative">${stats.total_bets - stats.won_bets - stats.returned_bets}</span> / 
                       <span class="neutral">${stats.returned_bets}</span>`
            },
            {
                title: 'Макс. Просадка',
                value: stats.max_drawdown,
                className: 'negative',
                format: (val) => formatNumber(val)
            },
            {
                title: 'ROI',
                value: stats.roi,
                className: stats.roi >= 0 ? 'positive' : 'negative',
                format: (val) => `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`
            },
            {
                title: 'Ср. Коэффициент',
                value: stats.avg_coefficient,
                format: (val) => val.toFixed(2)
            },
            {
                title: 'Серия Побед',
                value: stats.win_streak,
                className: 'positive'
            },
            {
                title: 'Серия Поражений',
                value: stats.loss_streak,
                className: 'negative'
            }
        ];
        
        statCards.forEach(card => {
            const statCard = document.createElement('div');
            statCard.className = 'stat-card';
            
            const title = document.createElement('h3');
            title.textContent = card.title;
            statCard.appendChild(title);
            
            const value = document.createElement('p');
            value.className = 'stat-value';
            if (card.className) value.classList.add(card.className);
            
            if (card.html) {
                value.innerHTML = card.html;
            } else {
                value.textContent = card.format ? card.format(card.value) : card.value;
            }
            
            statCard.appendChild(value);
            statsGrid.appendChild(statCard);
        });
    }

    // Обновление графика
    function updateChart(chartUrl) {
        const chartContainer = document.getElementById('chart-container');
        const chartImg = document.getElementById('chart-img');
        
        if (chartUrl) {
            chartImg.src = `data:image/png;base64,${chartUrl}`;
            chartContainer.style.display = 'block';
        } else {
            chartContainer.style.display = 'none';
        }
    }

    // Обновление таблицы ставок с пагинацией
    function updateBetsTable() {
        const tableBody = document.getElementById('bets-table-body');
        const noBetsMessage = document.getElementById('no-bets-message');
        const betsTable = document.getElementById('bets-table');
        const paginationControls = document.getElementById('pagination-controls');
        
        tableBody.innerHTML = '';
        
        if (allBets && allBets.length > 0) {
            noBetsMessage.style.display = 'none';
            betsTable.style.display = 'table';
            paginationControls.style.display = 'block';
            
            // Вычисляем индексы для текущей страницы
            const startIndex = (currentPage - 1) * betsPerPage;
            const endIndex = Math.min(startIndex + betsPerPage, allBets.length);
            const currentBets = allBets.slice(startIndex, endIndex);
            
            currentBets.forEach(bet => {
                const row = document.createElement('tr');
                
                if (bet.result === 'win') {
                    row.classList.add('win');
                } else if (bet.result === 'loss') {
                    row.classList.add('loss');
                } else if (bet.result === 'return' || bet.result === 'pending') {
                    row.classList.add('return');
                }
                
                let profit = 0;
                let profitClass = '';
                let resultText = '';
                
                if (bet.result === 'win') {
                    profit = bet.bet_amount * (bet.coefficient - 1);
                    profitClass = 'positive';
                    resultText = 'WIN';
                } else if (bet.result === 'loss') {
                    profit = -bet.bet_amount;
                    profitClass = 'negative';
                    resultText = 'LOSS';
                } else if (bet.result === 'return') {
                    profitClass = 'neutral';
                    resultText = 'Возврат';
                } else if (bet.result === 'pending') {
                    profitClass = 'neutral';
                    resultText = 'В ожидании';
                }
                
                row.innerHTML = `
                    <td>${bet.formatted_date}</td>
                    <td>${bet.event}</td>
                    <td>${parseFloat(bet.coefficient).toFixed(2)}</td>
                    <td>${formatNumber(parseFloat(bet.bet_amount))}</td>
                    <td class="${profitClass}">
                        ${bet.result === 'win' ? '+' : ''}${bet.result === 'loss' ? '-' : ''}${bet.result !== 'return' && bet.result !== 'pending' ? formatNumber(Math.abs(profit)) : '0'}
                    </td>
                    <td>${resultText}</td>
                    <td class="text-center">
                        <a href="#" class="action-btn delete-btn" data-id="${bet.id}" title="Удалить">
                            <i class="fas fa-trash"></i>
                        </a>
                        <a href="#" class="action-btn edit-btn" data-id="${bet.id}" title="Изменить">
                            <i class="fas fa-edit"></i>
                        </a>  
                    </td>
                `;
                
                tableBody.appendChild(row);
            });
            
            // Обновляем пагинацию
            updatePaginationControls();
            
            // Обработчики для кнопок удаления
            document.querySelectorAll('.delete-btn').forEach(btn => {
                btn.addEventListener('click', async function(e) {
                    e.preventDefault();
                    const betId = this.getAttribute('data-id');
                    
                    if (confirm('Вы уверены, что хотите удалить эту ставку?')) {
                        try {
                            const result = await eel.delete_bet(parseInt(betId))();
                            if (result.success) {
                                loadData();
                            } else {
                                alert(result.message);
                            }
                        } catch (error) {
                            console.error('Ошибка при удалении ставки:', error);
                            alert('Произошла ошибка при удалении ставки.');
                        }
                    }
                });
            });
            
            // Обработчики для кнопок редактирования
            document.querySelectorAll('.edit-btn').forEach(btn => {
                btn.addEventListener('click', async function(e) {
                    e.preventDefault();
                    const betId = this.getAttribute('data-id');
                    
                    try {
                        const result = await eel.get_bet(parseInt(betId))();
                        if (result.success) {
                            const bet = result.bet;
                            editingBetId = bet.id;
                            
                            // Заполняем форму данными ставки
                            document.getElementById('date').value = bet.formatted_date;
                            document.getElementById('event').value = bet.event;
                            document.getElementById('coefficient').value = bet.coefficient;
                            document.getElementById('bet_amount').value = bet.bet_amount;
                            
                            // Сбрасываем результат на значение по умолчанию
                            document.getElementById('result').value = 'Результат';
                            
                            // Меняем текст кнопки
                            const submitBtn = document.getElementById('submit-btn');
                            submitBtn.innerHTML = '<i class="fas fa-save"></i> Записать';
                            
                            // Прокручиваем к форме
                            document.getElementById('bet-form').scrollIntoView({ behavior: 'smooth' });
                        } else {
                            alert(result.message);
                        }
                    } catch (error) {
                        console.error('Ошибка при получении ставки:', error);
                        alert('Произошла ошибка при получении данных ставки.');
                    }
                });
            });
        } else {
            noBetsMessage.textContent = 'Нет данных о ставках';
            noBetsMessage.style.display = 'block';
            betsTable.style.display = 'none';
            paginationControls.style.display = 'none';
        }
    }

    // Обновление элементов пагинации
    function updatePaginationControls() {
        const totalPages = Math.ceil(allBets.length / betsPerPage);
        const pageNumbers = document.getElementById('page-numbers');
        pageNumbers.innerHTML = '';
        
        // Определяем диапазон страниц для отображения
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);
        
        // Если текущая страница в начале, показываем больше страниц справа
        if (currentPage <= 3) {
            endPage = Math.min(5, totalPages);
        }
        // Если текущая страница в конце, показываем больше страниц слева
        else if (currentPage >= totalPages - 2) {
            startPage = Math.max(1, totalPages - 4);
        }
        
        // Кнопка "Предыдущая"
        document.getElementById('prev-page').classList.toggle('disabled', currentPage === 1);
        
        // Номера страниц
        for (let i = startPage; i <= endPage; i++) {
            const pageLink = document.createElement('a');
            pageLink.href = '#';
            pageLink.textContent = i;
            pageLink.className = 'page-number';
            if (i === currentPage) {
                pageLink.classList.add('active');
            }
            pageLink.addEventListener('click', (e) => {
                e.preventDefault();
                currentPage = i;
                updateBetsTable();
            });
            pageNumbers.appendChild(pageLink);
        }
        
        // Кнопка "Следующая"
        document.getElementById('next-page').classList.toggle('disabled', currentPage === totalPages);
    }

    // Обработчики для кнопок пагинации
    document.getElementById('prev-page').addEventListener('click', function(e) {
        e.preventDefault();
        if (currentPage > 1) {
            currentPage--;
            updateBetsTable();
        }
    });

    document.getElementById('next-page').addEventListener('click', function(e) {
        e.preventDefault();
        const totalPages = Math.ceil(allBets.length / betsPerPage);
        if (currentPage < totalPages) {
            currentPage++;
            updateBetsTable();
        }
    });

    // Функция валидации даты
    function validateDate(dateStr) {
        const normalizedDateStr = dateStr.replace(/,/g, '.');
        const regex = /^\d{2}\.\d{2}\.\d{4}$/;
        if (!regex.test(normalizedDateStr)) return false;
        
        const parts = normalizedDateStr.split('.');
        const day = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10);
        const year = parseInt(parts[2], 10);
        
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;
        
        return true;
    }

    // Инициализация приложения
    loadData();
    
    // Элементы формы
    const dateInput = document.getElementById('date');
    const dateError = document.getElementById('date-error');
    const form = document.getElementById('bet-form');
    const submitBtn = document.getElementById('submit-btn');
    
    // Устанавливаем текущую дату по умолчанию
    const today = new Date();
    const day = String(today.getDate()).padStart(2, '0');
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const year = today.getFullYear();
    dateInput.value = `${day}.${month}.${year}`;
    
    // Обработчик ввода для автоматической замены запятых на точки
    dateInput.addEventListener('input', function() {
        this.value = this.value.replace(/,/g, '.');
        
        if (validateDate(this.value)) {
            dateError.style.display = 'none';
            this.style.borderColor = '';
        } else {
            this.style.borderColor = 'var(--negative)';
            dateError.textContent = 'Введите в формате 17.07.2025';
        }
    });
    
    // Обработчик отправки формы
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const dateValue = dateInput.value.replace(/,/g, '.');
        if (!validateDate(dateValue)) {
            dateError.style.display = 'block';
            dateInput.focus();
            return;
        }
        
        const formData = {
            date: dateValue,
            event: document.getElementById('event').value,
            coefficient: document.getElementById('coefficient').value,
            bet_amount: document.getElementById('bet_amount').value,
            result: document.getElementById('result').value
        };
        
        if (formData.result === 'Результат') {
            alert('Пожалуйста, выберите результат ставки');
            return;
        }
        
        // Преобразуем результат в нужный формат
        if (formData.result === 'WIN') formData.result = 'win';
        else if (formData.result === 'LOSS') formData.result = 'loss';
        else if (formData.result === 'Возврат') formData.result = 'return';
        else if (formData.result === 'Ожидание') formData.result = 'pending';
        
        try {
            let result;
            if (editingBetId) {
                // Редактируем существующую ставку
                result = await eel.update_bet(editingBetId, formData)();
            } else {
                // Добавляем новую ставку
                result = await eel.add_bet(formData)();
            }
            
            if (result.success) {
                // Сбрасываем форму
                document.getElementById('event').value = '';
                document.getElementById('coefficient').value = '';
                document.getElementById('bet_amount').value = '';
                document.getElementById('result').value = 'Результат';
                
                // Возвращаем кнопку в исходное состояние
                submitBtn.innerHTML = '<i class="fas fa-plus"></i> Добавить';
                editingBetId = null;
                
                // Обновляем данные
                loadData();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error('Ошибка при добавлении/обновлении ставки:', error);
            alert('Произошла ошибка при добавлении/обновлении ставки.');
        }
    });
    
    // Обработчик для кнопки экспорта в Excel
    document.getElementById('export-excel-btn').addEventListener('click', async function() {
        try {
            const result = await eel.export_to_excel()();
            
            if (result.success) {
                const link = document.createElement('a');
                link.href = `data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,${result.data}`;
                link.download = result.filename;
                link.click();
            } else {
                alert(result.message);
            }
        } catch (error) {
            console.error('Ошибка при экспорте в Excel:', error);
            alert('Произошла ошибка при экспорте данных.');
        }
    });
    
    // Обработчик для кнопки импорта из Excel
    document.getElementById('import-excel-btn').addEventListener('click', function() {
        document.getElementById('excel-file-input').click();
    });
    
    // Обработчик загрузки файла Excel
    document.getElementById('excel-file-input').addEventListener('change', async function() {
        if (this.files.length > 0) {
            if (confirm('Внимание! Все существующие данные будут удалены и заменены на данные из файла. Продолжить?')) {
                const file = this.files[0];
                const reader = new FileReader();
                
                reader.onload = async function(e) {
                    try {
                        const result = await eel.import_from_excel(e.target.result)();
                        
                        if (result.success) {
                            document.getElementById('excel-file-input').value = '';
                            loadData();
                            alert(result.message);
                        } else {
                            alert(result.message);
                        }
                    } catch (error) {
                        console.error('Ошибка при импорте из Excel:', error);
                        alert('Произошла ошибка при импорте данных.');
                    }
                };
                
                reader.readAsDataURL(file);
            } else {
                this.value = '';
            }
        }
    });
});

// Обработчик закрытия окна
window.addEventListener('beforeunload', async function() {
    try {
        await eel.close_app()();
    } catch (e) {
        console.error("Ошибка при закрытии:", e);
    }
});