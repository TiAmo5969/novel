// D:\py\flaskProject\static\js\main.js
document.addEventListener('DOMContentLoaded', () => {
    // 搜索功能增强
    initSearchEnhancements();
    
    // // 夜间模式切换
    // const toggle = document.createElement('button');
    // toggle.textContent = '切换夜间模式';
    // toggle.className = 'fixed top-4 right-4 bg-blue-600 text-white p-2 rounded';
    // document.body.appendChild(toggle);
    // toggle.addEventListener('click', () => {
    //     document.body.classList.toggle('dark');
    //     localStorage.setItem('darkMode', document.body.classList.contains('dark'));
    // });
    // if (localStorage.getItem('darkMode') === 'true') {
    //     document.body.classList.add('dark');
    // }

    // 字体大小调整
    // const fontSelect = document.createElement('select');
    // fontSelect.innerHTML = `
    //     <option value="16px">正常</option>
    //     <option value="18px">较大</option>
    //     <option value="20px">超大</option>
    // `;
    // fontSelect.className = 'fixed top-12 right-4 p-2 rounded';
    // document.body.appendChild(fontSelect);
    // fontSelect.addEventListener('change', () => {
    //     document.body.style.fontSize = fontSelect.value;
    //     localStorage.setItem('fontSize', fontSelect.value);
    // });
    // if (localStorage.getItem('fontSize')) {
    //     document.body.style.fontSize = localStorage.getItem('fontSize');
    // }
});

// 搜索功能增强
function initSearchEnhancements() {
    // 获取所有搜索输入框
    const searchInputs = document.querySelectorAll('input[name="q"]');
    
    searchInputs.forEach(input => {
        // 添加搜索历史功能
        loadSearchHistory(input);
        
        // 监听输入事件，提供实时搜索建议
        let searchTimeout;
        input.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            const query = this.value.trim();
            
            if (query.length >= 2) {
                searchTimeout = setTimeout(() => {
                    // 这里可以添加实时搜索建议功能
                    // 目前先保存搜索历史
                    saveSearchHistory(query);
                }, 300);
            }
        });
        
        // 监听回车键
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                const query = this.value.trim();
                if (query) {
                    saveSearchHistory(query);
                }
            }
        });
        
        // 添加搜索建议下拉框
        createSearchSuggestions(input);
    });
}

// 搜索历史功能
function saveSearchHistory(query) {
    if (!query || query.length < 2) return;
    
    let history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    
    // 移除重复项
    history = history.filter(item => item !== query);
    
    // 添加到开头
    history.unshift(query);
    
    // 限制历史记录数量
    if (history.length > 10) {
        history = history.slice(0, 10);
    }
    
    localStorage.setItem('searchHistory', JSON.stringify(history));
}

function loadSearchHistory(input) {
    const history = JSON.parse(localStorage.getItem('searchHistory') || '[]');
    
    // 如果有历史记录，在输入框获得焦点时显示
    input.addEventListener('focus', function() {
        if (history.length > 0 && !this.value) {
            showSearchHistory(this, history);
        }
    });
    
    input.addEventListener('blur', function() {
        // 延迟隐藏，以便用户能点击建议项
        setTimeout(() => {
            hideSearchHistory(this);
        }, 200);
    });
}

// 创建搜索建议下拉框
function createSearchSuggestions(input) {
    const suggestionsContainer = document.createElement('div');
    suggestionsContainer.className = 'search-suggestions absolute top-full left-0 right-0 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg shadow-lg z-50 hidden';
    suggestionsContainer.style.maxHeight = '200px';
    suggestionsContainer.style.overflowY = 'auto';
    
    // 将建议框插入到输入框的父容器中
    const parent = input.parentElement;
    if (parent.style.position !== 'relative') {
        parent.style.position = 'relative';
    }
    parent.appendChild(suggestionsContainer);
}

function showSearchHistory(input, history) {
    const suggestionsContainer = input.parentElement.querySelector('.search-suggestions');
    if (!suggestionsContainer) return;
    
    suggestionsContainer.innerHTML = '';
    
    // 添加历史记录标题
    const title = document.createElement('div');
    title.className = 'px-4 py-2 text-xs font-semibold text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-600';
    title.textContent = '搜索历史';
    suggestionsContainer.appendChild(title);
    
    // 添加历史记录项
    history.slice(0, 5).forEach(item => {
        const suggestion = document.createElement('div');
        suggestion.className = 'px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer flex items-center justify-between';
        suggestion.innerHTML = `
            <span>${item}</span>
            <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/>
            </svg>
        `;
        
        suggestion.addEventListener('click', function() {
            input.value = item;
            input.focus();
            hideSearchHistory(input);
            
            // 触发表单提交
            const form = input.closest('form');
            if (form) {
                form.submit();
            }
        });
        
        suggestionsContainer.appendChild(suggestion);
    });
    
    // 添加清除历史按钮
    const clearButton = document.createElement('div');
    clearButton.className = 'px-4 py-2 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer text-center border-t border-gray-200 dark:border-gray-600';
    clearButton.textContent = '清除搜索历史';
    clearButton.addEventListener('click', function() {
        localStorage.removeItem('searchHistory');
        hideSearchHistory(input);
    });
    suggestionsContainer.appendChild(clearButton);
    
    suggestionsContainer.classList.remove('hidden');
}

function hideSearchHistory(input) {
    const suggestionsContainer = input.parentElement.querySelector('.search-suggestions');
    if (suggestionsContainer) {
        suggestionsContainer.classList.add('hidden');
    }
}

// 高亮搜索关键词
function highlightSearchTerms(text, query) {
    if (!query || !text) return text;
    
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-1 rounded">$1</mark>');
}