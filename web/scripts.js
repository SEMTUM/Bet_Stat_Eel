document.addEventListener('DOMContentLoaded', function() {
    function formatNumber(num, decimals = 0) {
        return num.toFixed(decimals).replace(/(\d)(?=(\d{3})+(?!\d))/g, '$1 ');
    }

    let editingBetId = null;
    let currentPage = 1;
    const betsPerPage = 50;
    let allBets = [];
    let sources = [];
    let allMonths = [];

    const modal = document.getElementById('source-modal');
    const addSourceFormBtn = document.getElementById('add-source-form-btn');
    const closeModalBtn = document.querySelector('.close-modal');
    const confirmAddSourceBtn = document.getElementById('confirm-add-source');
    const newSourceInput = document.getElementById('new-source-input');

    if (addSourceFormBtn) {
        addSourceFormBtn.addEventListener('click', function() {
            if (modal) modal.style.display = 'block';
            if (newSourceInput) newSourceInput.focus();
        });
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', function() {
            if (modal) modal.style.display = 'none';
            if (newSourceInput) newSourceInput.value = '';
        });
    }

    window.addEventListener('click', function(event) {
        if (event.target === modal && modal) {
            modal.style.display = 'none';
            if (newSourceInput) newSourceInput.value = '';
        }
    });

    if (confirmAddSourceBtn && newSourceInput) {
        confirmAddSourceBtn.addEventListener('click', function() {
            const newSource = newSourceInput.value.trim();
            if (!newSource) {
                alert('Введите название источника');
                return;
            }
            
            if (modal) modal.style.display = 'none';
            newSourceInput.value = '';
            
            const sourceSelect = document.getElementById('source');
            if (sourceSelect) {
                const option = document.createElement('option');
                option.value = newSource;
                option.textContent = newSource;
                sourceSelect.appendChild(option);
                sourceSelect.value = newSource;
            }
        });

        newSourceInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                confirmAddSourceBtn.click();
            }
        });
    }

    async function loadData(date_filter = null, coeff_filter = null, source_filter = null) {
        try {
            const data = await eel.calculate_stats(date_filter, coeff_filter, source_filter)();
            updateStats(data.stats);
            updateChart(data.chart_url);
            allBets = data.bets;
            sources = data.sources;
            updateSourcesDropdown();
            
            if (allMonths.length === 0) {
                const uniqueMonths = new Set();
                allBets.forEach(function(bet) {
                    const dateParts = bet.date.split('-');
                    if (dateParts.length === 3) {
                        const month = dateParts[1];
                        uniqueMonths.add(month);
                    }
                });
                allMonths = Array.from(uniqueMonths).sort((a, b) => b.localeCompare(a));
            }
            
            updateMonthsDropdown();
            updateBetsTable();
        } catch (error) {
            console.error('Ошибка при загрузке данных:', error);
            alert('Произошла ошибка при загрузке данных. Пожалуйста, попробуйте снова.');
        }
    }

    function updateSourcesDropdown() {
        const sourceSelect = document.getElementById('source');
        const sourceFilterSelect = document.getElementById('source-filter');
        
        if (!sourceSelect || !sourceFilterSelect) return;
        
        const currentSource = sourceSelect.value;
        const currentFilterSource = sourceFilterSelect.value;
        
        sourceSelect.innerHTML = '<option value="Не указан">Источник</option>';
        sourceFilterSelect.innerHTML = '<option value="all">Все источники</option><option value="Не указан">Не указан</option>';
        
        sources.forEach(function(source) {
            const option = document.createElement('option');
            option.value = source;
            option.textContent = source;
            sourceSelect.appendChild(option.cloneNode(true));
            sourceFilterSelect.appendChild(option);
        });
        
        if (currentSource && Array.from(sourceSelect.options).some(function(opt) { return opt.value === currentSource; })) {
            sourceSelect.value = currentSource;
        }
        
        if (currentFilterSource && Array.from(sourceFilterSelect.options).some(function(opt) { return opt.value === currentFilterSource; })) {
            sourceFilterSelect.value = currentFilterSource;
        }
    }

    function updateMonthsDropdown() {
    const monthNames = {
        '01': 'Январь', '02': 'Февраль', '03': 'Март', 
        '04': 'Апрель', '05': 'Май', '06': 'Июнь',
        '07': 'Июль', '08': 'Август', '09': 'Сентябрь',
        '10': 'Октябрь', '11': 'Ноябрь', '12': 'Декабрь'
    };
    
    const monthMapping = {
        'january': '01', 'february': '02', 'march': '03',
        'april': '04', 'may': '05', 'june': '06',
        'july': '07', 'august': '08', 'september': '09',
        'october': '10', 'november': '11', 'december': '12'
    };
    
    const dateFilter = document.getElementById('date-filter');
    if (!dateFilter) return;
    
    const currentValue = dateFilter.value;
    
    dateFilter.innerHTML = '<option value="all">Все время</option>';
    
    // Получаем доступные месяцы из данных
    const availableMonths = allMonths || [];
    
    availableMonths.forEach(function(month) {
        const monthKey = Object.keys(monthMapping).find(key => monthMapping[key] === month);
        if (monthKey && monthNames[month]) {
            const option = document.createElement('option');
            option.value = monthKey;
            option.textContent = monthNames[month];
            dateFilter.appendChild(option);
        }
    });
    
    if (currentValue && Array.from(dateFilter.options).some(opt => opt.value === currentValue)) {
        dateFilter.value = currentValue;
    }
}

    function updateStats(stats) {
        const statsGrid = document.getElementById('stats-grid');
        if (!statsGrid) return;
        
        statsGrid.innerHTML = '';
        
        const statCards = [
            {
                title: 'Прибыль',
                value: stats.total_profit,
                className: stats.total_profit >= 0 ? 'positive' : 'negative',
                format: function(val) { return `${val >= 0 ? '+' : ''}${formatNumber(val)}`; }
            },
            {
                title: 'Проходимость',
                value: stats.pass_rate,
                format: function(val) { return `${val.toFixed(1)}%`; }
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
                format: function(val) { return formatNumber(val); }
            },
            {
                title: 'ROI',
                value: stats.roi,
                className: stats.roi >= 0 ? 'positive' : 'negative',
                format: function(val) { return `${val >= 0 ? '+' : ''}${val.toFixed(1)}%`; }
            },
            {
                title: 'Ср. Коэффициент',
                value: stats.avg_coefficient,
                format: function(val) { return val.toFixed(2); }
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
        
        statCards.forEach(function(card) {
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

    function updateChart(chartUrl) {
        const chartContainer = document.getElementById('chart-container');
        const chartImg = document.getElementById('chart-img');
        
        if (!chartContainer || !chartImg) return;
        
        if (chartUrl) {
            chartImg.src = `data:image/png;base64,${chartUrl}`;
            chartContainer.style.display = 'block';
        } else {
            chartContainer.style.display = 'none';
        }
    }

    function updateBetsTable() {
        const tableBody = document.getElementById('bets-table-body');
        const noBetsMessage = document.getElementById('no-bets-message');
        const betsTable = document.getElementById('bets-table');
        const paginationControls = document.getElementById('pagination-controls');
        
        if (!tableBody || !noBetsMessage || !betsTable || !paginationControls) return;
        
        tableBody.innerHTML = '';
        
        if (allBets && allBets.length > 0) {
            noBetsMessage.style.display = 'none';
            betsTable.style.display = 'table';
            paginationControls.style.display = 'block';
            
            const startIndex = (currentPage - 1) * betsPerPage;
            const endIndex = Math.min(startIndex + betsPerPage, allBets.length);
            const currentBets = allBets.slice(startIndex, endIndex);
            
            currentBets.forEach(function(bet) {
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
                    <td>${bet.source || 'Не указан'}</td>
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
            
            updatePaginationControls();
            
            document.querySelectorAll('.delete-btn').forEach(function(btn) {
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
            
            document.querySelectorAll('.edit-btn').forEach(function(btn) {
                btn.addEventListener('click', async function(e) {
                    e.preventDefault();
                    const betId = this.getAttribute('data-id');
                    
                    try {
                        const result = await eel.get_bet(parseInt(betId))();
                        if (result.success) {
                            const bet = result.bet;
                            editingBetId = bet.id;
                            
                            document.getElementById('date').value = bet.formatted_date;
                            document.getElementById('event').value = bet.event;
                            document.getElementById('coefficient').value = bet.coefficient;
                            document.getElementById('bet_amount').value = bet.bet_amount;
                            document.getElementById('source').value = bet.source || 'Не указан';
                            
                            document.getElementById('result').value = 'Результат';
                            
                            const submitBtn = document.getElementById('submit-btn');
                            if (submitBtn) submitBtn.innerHTML = '<i class="fas fa-save"></i> Записать';
                            
                            const betForm = document.getElementById('bet-form');
                            if (betForm) betForm.scrollIntoView({ behavior: 'smooth' });
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

    function updatePaginationControls() {
        const totalPages = Math.ceil(allBets.length / betsPerPage);
        const pageNumbers = document.getElementById('page-numbers');
        const prevPage = document.getElementById('prev-page');
        const nextPage = document.getElementById('next-page');
        
        if (!pageNumbers || !prevPage || !nextPage) return;
        
        pageNumbers.innerHTML = '';
        
        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(totalPages, currentPage + 2);
        
        if (currentPage <= 3) {
            endPage = Math.min(5, totalPages);
        }
        else if (currentPage >= totalPages - 2) {
            startPage = Math.max(1, totalPages - 4);
        }
        
        prevPage.classList.toggle('disabled', currentPage === 1);
        
        for (let i = startPage; i <= endPage; i++) {
            const pageLink = document.createElement('a');
            pageLink.href = '#';
            pageLink.textContent = i;
            pageLink.className = 'pagination-btn';
            if (i === currentPage) {
                pageLink.classList.add('active');
            }
            pageLink.addEventListener('click', function(e) {
                e.preventDefault();
                currentPage = i;
                updateBetsTable();
            });
            pageNumbers.appendChild(pageLink);
        }
        
        nextPage.classList.toggle('disabled', currentPage === totalPages);
    }

    const prevPageBtn = document.getElementById('prev-page');
    const nextPageBtn = document.getElementById('next-page');
    
    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (currentPage > 1) {
                currentPage--;
                updateBetsTable();
            }
        });
    }
    
    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', function(e) {
            e.preventDefault();
            const totalPages = Math.ceil(allBets.length / betsPerPage);
            if (currentPage < totalPages) {
                currentPage++;
                updateBetsTable();
            }
        });
    }

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

    const dateFilter = document.getElementById('date-filter');
    const sourceFilter = document.getElementById('source-filter');
    const resetFiltersBtn = document.getElementById('reset-filters');
    const applyFiltersBtn = document.getElementById('apply-filters');
    const minCoeffInput = document.getElementById('min-coeff');
    const maxCoeffInput = document.getElementById('max-coeff');

    function resetFilters() {
        if (dateFilter) dateFilter.value = 'all';
        if (sourceFilter) sourceFilter.value = 'all';
        if (minCoeffInput) minCoeffInput.value = '';
        if (maxCoeffInput) maxCoeffInput.value = '';
        loadData();
    }

    function applyFilters() {
        const dateValue = dateFilter ? dateFilter.value : null;
        const sourceValue = sourceFilter ? sourceFilter.value : null;
        
        let coeffFilter = null;
        if (minCoeffInput && maxCoeffInput && minCoeffInput.value && maxCoeffInput.value) {
            coeffFilter = { 
                min: parseFloat(minCoeffInput.value), 
                max: parseFloat(maxCoeffInput.value) 
            };
        }
        
        loadData(dateValue, coeffFilter, sourceValue);
    }

    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener('click', function(e) {
            e.preventDefault();
            resetFilters();
        });
    }

    if (applyFiltersBtn) {
        applyFiltersBtn.addEventListener('click', function(e) {
            e.preventDefault();
            applyFilters();
        });
    }

    loadData();
    
    const dateInput = document.getElementById('date');
    const dateError = document.getElementById('date-error');
    const form = document.getElementById('bet-form');
    const submitBtn = document.getElementById('submit-btn');
    
    if (dateInput) {
        const today = new Date();
        const day = String(today.getDate()).padStart(2, '0');
        const month = String(today.getMonth() + 1).padStart(2, '0');
        const year = today.getFullYear();
        dateInput.value = `${day}.${month}.${year}`;
        
        dateInput.addEventListener('input', function() {
            this.value = this.value.replace(/,/g, '.');
            
            if (validateDate(this.value)) {
                if (dateError) dateError.style.display = 'none';
                this.style.borderColor = '';
            } else {
                this.style.borderColor = 'var(--negative)';
                if (dateError) {
                    dateError.textContent = 'Введите в формате 17.07.2025';
                    dateError.style.display = 'block';
                }
            }
        });
    }
    
    if (form) {
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            if (!dateInput || !validateDate(dateInput.value.replace(/,/g, '.'))) {
                if (dateError) {
                    dateError.style.display = 'block';
                    if (dateInput) dateInput.focus();
                }
                return;
            }
            
            const resultSelect = document.getElementById('result');
            if (resultSelect && resultSelect.value === 'Результат') {
                alert('Пожалуйста, выберите результат ставки');
                return;
            }
            
            const formData = {
                date: dateInput ? dateInput.value.replace(/,/g, '.') : '',
                event: document.getElementById('event') ? document.getElementById('event').value : '',
                coefficient: document.getElementById('coefficient') ? document.getElementById('coefficient').value : '',
                bet_amount: document.getElementById('bet_amount') ? document.getElementById('bet_amount').value : '',
                result: resultSelect ? resultSelect.value : '',
                source: document.getElementById('source') ? document.getElementById('source').value : ''
            };
            
            if (formData.result === 'WIN') formData.result = 'win';
            else if (formData.result === 'LOSS') formData.result = 'loss';
            else if (formData.result === 'Возврат') formData.result = 'return';
            else if (formData.result === 'Ожидание') formData.result = 'pending';
            
            try {
                let result;
                if (editingBetId) {
                    result = await eel.update_bet(editingBetId, formData)();
                } else {
                    result = await eel.add_bet(formData)();
                }
                
                if (result.success) {
                    const eventInput = document.getElementById('event');
                    const coefficientInput = document.getElementById('coefficient');
                    const betAmountInput = document.getElementById('bet_amount');
                    const resultSelect = document.getElementById('result');
                    const sourceSelect = document.getElementById('source');
                    
                    if (eventInput) eventInput.value = '';
                    if (coefficientInput) coefficientInput.value = '';
                    if (betAmountInput) betAmountInput.value = '';
                    if (resultSelect) resultSelect.value = 'Результат';
                    if (sourceSelect) sourceSelect.value = 'Не указан';
                    
                    if (submitBtn) submitBtn.innerHTML = '<i class="fas fa-plus"></i> Добавить';
                    editingBetId = null;
                    
                    loadData();
                } else {
                    alert(result.message);
                }
            } catch (error) {
                console.error('Ошибка при добавлении/обновлении ставки:', error);
                alert('Произошла ошибка при добавлении/обновлении ставки.');
            }
        });
    }
    
    const exportExcelBtn = document.getElementById('export-excel-btn');
    if (exportExcelBtn) {
        exportExcelBtn.addEventListener('click', async function() {
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
    }
    
    const importExcelBtn = document.getElementById('import-excel-btn');
    if (importExcelBtn) {
        importExcelBtn.addEventListener('click', function() {
            const fileInput = document.getElementById('excel-file-input');
            if (fileInput) fileInput.click();
        });
    }
    
    const excelFileInput = document.getElementById('excel-file-input');
    if (excelFileInput) {
        excelFileInput.addEventListener('change', async function() {
            if (this.files.length > 0) {
                if (confirm('Внимание! Все существующие данные будут удалены и заменены на данные из файла. Продолжить?')) {
                    const file = this.files[0];
                    const reader = new FileReader();
                    
                    reader.onload = async function(e) {
                        try {
                            const result = await eel.import_from_excel(e.target.result)();
                            
                            if (result.success) {
                                const fileInput = document.getElementById('excel-file-input');
                                if (fileInput) fileInput.value = '';
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
    }
});

window.addEventListener('beforeunload', async function() {
    try {
        await eel.close_app()();
    } catch (e) {
        console.error("Ошибка при закрытии:", e);
    }
});
// ....