/**
 * Arbion AI Trading Platform - Main JavaScript
 * Handles common functionality, interactions, and UI enhancements
 */

// Global configuration
const ArbionConfig = {
    apiBaseUrl: window.location.origin,
    debounceDelay: 300,
    toastDuration: 5000,
    chartColors: {
        primary: '#1652f0',
        success: '#05d9a1',
        danger: '#f04438',
        warning: '#fbbf24',
        info: '#3b82f6'
    }
};

// Utility functions
const Utils = {
    /**
     * Debounce function to limit rapid function calls
     */
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * Format currency values
     */
    formatCurrency: function(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },

    /**
     * Format percentage values
     */
    formatPercentage: function(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'percent',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value / 100);
    },

    /**
     * Format date/time values
     */
    formatDateTime: function(dateString) {
        const date = new Date(dateString);
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(date);
    },

    /**
     * Show loading state on buttons
     */
    showButtonLoading: function(button, text = 'Loading...') {
        const originalText = button.textContent;
        button.disabled = true;
        button.innerHTML = `
            <div class="loading-spinner mr-2"></div>
            ${text}
        `;
        return originalText;
    },

    /**
     * Hide loading state on buttons
     */
    hideButtonLoading: function(button, originalText) {
        button.disabled = false;
        button.innerHTML = originalText;
    },

    /**
     * Show toast notification
     */
    showToast: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} fixed top-4 right-4 z-50 max-w-sm`;
        toast.innerHTML = `
            <div class="flex items-center justify-between">
                <span>${message}</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-white hover:text-gray-300">
                    <i data-feather="x" class="w-4 h-4"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Initialize feather icons for the toast
        feather.replace();
        
        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, ArbionConfig.toastDuration);
    },

    /**
     * Copy text to clipboard
     */
    copyToClipboard: function(text) {
        navigator.clipboard.writeText(text).then(() => {
            Utils.showToast('Copied to clipboard!', 'success');
        }).catch(() => {
            Utils.showToast('Failed to copy to clipboard', 'error');
        });
    },

    /**
     * Validate form fields
     */
    validateForm: function(form) {
        const errors = [];
        const requiredFields = form.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                errors.push(`${field.name || field.id} is required`);
                field.classList.add('border-red-500');
            } else {
                field.classList.remove('border-red-500');
            }
        });
        
        // Email validation
        const emailFields = form.querySelectorAll('input[type="email"]');
        emailFields.forEach(field => {
            if (field.value && !Utils.isValidEmail(field.value)) {
                errors.push('Please enter a valid email address');
                field.classList.add('border-red-500');
            }
        });
        
        // Password validation
        const passwordFields = form.querySelectorAll('input[type="password"]');
        passwordFields.forEach(field => {
            if (field.value && field.value.length < 8) {
                errors.push('Password must be at least 8 characters long');
                field.classList.add('border-red-500');
            }
        });
        
        return errors;
    },

    /**
     * Email validation
     */
    isValidEmail: function(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    /**
     * Generate random ID
     */
    generateId: function() {
        return 'id_' + Math.random().toString(36).substr(2, 9);
    }
};

// API Helper functions
const API = {
    /**
     * Test API connection
     */
    testConnection: function(provider, callback) {
        const formData = new FormData();
        formData.append('provider', provider);
        
        fetch('/test-api-connection', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (callback) callback(data);
        })
        .catch(error => {
            console.error('API test failed:', error);
            if (callback) callback({ success: false, message: 'Connection test failed' });
        });
    },

    /**
     * Submit form via AJAX
     */
    submitForm: function(form, callback) {
        const formData = new FormData(form);
        
        fetch(form.action || window.location.href, {
            method: form.method || 'POST',
            body: formData
        })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            throw new Error('Network response was not ok');
        })
        .then(data => {
            if (callback) callback(data);
        })
        .catch(error => {
            console.error('Form submission failed:', error);
            if (callback) callback({ success: false, message: 'Form submission failed' });
        });
    }
};

// UI Enhancement functions
const UI = {
    /**
     * Initialize tooltips
     */
    initTooltips: function() {
        const tooltipElements = document.querySelectorAll('[data-tooltip]');
        
        tooltipElements.forEach(element => {
            element.addEventListener('mouseenter', function(e) {
                const tooltip = document.createElement('div');
                tooltip.className = 'absolute z-50 px-2 py-1 text-xs text-white bg-gray-800 rounded shadow-lg';
                tooltip.textContent = e.target.dataset.tooltip;
                tooltip.style.top = e.target.offsetTop - 30 + 'px';
                tooltip.style.left = e.target.offsetLeft + 'px';
                tooltip.id = 'tooltip-' + Utils.generateId();
                
                document.body.appendChild(tooltip);
                
                e.target.addEventListener('mouseleave', function() {
                    const tooltipEl = document.getElementById(tooltip.id);
                    if (tooltipEl) tooltipEl.remove();
                }, { once: true });
            });
        });
    },

    /**
     * Initialize modals
     */
    initModals: function() {
        // Close modals when clicking outside
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('modal-backdrop')) {
                const modal = e.target.closest('.modal');
                if (modal) {
                    modal.classList.add('hidden');
                    modal.classList.remove('flex');
                }
            }
        });

        // Close modals with Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                const visibleModals = document.querySelectorAll('.modal:not(.hidden)');
                visibleModals.forEach(modal => {
                    modal.classList.add('hidden');
                    modal.classList.remove('flex');
                });
            }
        });
    },

    /**
     * Initialize dropdown menus
     */
    initDropdowns: function() {
        const dropdownTriggers = document.querySelectorAll('[data-dropdown-trigger]');
        
        dropdownTriggers.forEach(trigger => {
            trigger.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                const dropdownId = trigger.dataset.dropdownTrigger;
                const dropdown = document.getElementById(dropdownId);
                
                if (dropdown) {
                    dropdown.classList.toggle('hidden');
                }
            });
        });

        // Close dropdowns when clicking outside
        document.addEventListener('click', function() {
            const dropdowns = document.querySelectorAll('[data-dropdown]');
            dropdowns.forEach(dropdown => {
                dropdown.classList.add('hidden');
            });
        });
    },

    /**
     * Initialize tabs
     */
    initTabs: function() {
        const tabButtons = document.querySelectorAll('[data-tab-button]');
        
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                const tabGroup = button.dataset.tabGroup;
                const tabTarget = button.dataset.tabButton;
                
                // Remove active class from all buttons in group
                const groupButtons = document.querySelectorAll(`[data-tab-group="${tabGroup}"]`);
                groupButtons.forEach(btn => btn.classList.remove('active'));
                
                // Add active class to clicked button
                button.classList.add('active');
                
                // Hide all tab contents in group
                const tabContents = document.querySelectorAll(`[data-tab-group="${tabGroup}"][data-tab-content]`);
                tabContents.forEach(content => content.classList.add('hidden'));
                
                // Show target tab content
                const targetContent = document.querySelector(`[data-tab-content="${tabTarget}"]`);
                if (targetContent) {
                    targetContent.classList.remove('hidden');
                }
            });
        });
    },

    /**
     * Initialize search functionality
     */
    initSearch: function() {
        const searchInputs = document.querySelectorAll('[data-search]');
        
        searchInputs.forEach(input => {
            const searchHandler = Utils.debounce(function() {
                const searchTerm = input.value.toLowerCase();
                const searchTarget = input.dataset.search;
                const searchItems = document.querySelectorAll(`[data-search-item="${searchTarget}"]`);
                
                searchItems.forEach(item => {
                    const searchableText = item.textContent.toLowerCase();
                    if (searchableText.includes(searchTerm)) {
                        item.style.display = '';
                    } else {
                        item.style.display = 'none';
                    }
                });
            }, ArbionConfig.debounceDelay);
            
            input.addEventListener('input', searchHandler);
        });
    },

    /**
     * Initialize sorting functionality
     */
    initSorting: function() {
        const sortButtons = document.querySelectorAll('[data-sort]');
        
        sortButtons.forEach(button => {
            button.addEventListener('click', function() {
                const sortBy = button.dataset.sort;
                const sortOrder = button.dataset.sortOrder || 'asc';
                const sortTarget = button.dataset.sortTarget;
                
                const container = document.querySelector(`[data-sort-container="${sortTarget}"]`);
                if (!container) return;
                
                const items = Array.from(container.children);
                
                items.sort((a, b) => {
                    const aValue = a.dataset[sortBy] || a.textContent;
                    const bValue = b.dataset[sortBy] || b.textContent;
                    
                    if (sortOrder === 'asc') {
                        return aValue.localeCompare(bValue);
                    } else {
                        return bValue.localeCompare(aValue);
                    }
                });
                
                // Update sort order for next click
                button.dataset.sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
                
                // Update visual indicator
                const sortButtons = document.querySelectorAll(`[data-sort-target="${sortTarget}"]`);
                sortButtons.forEach(btn => btn.classList.remove('sort-active'));
                button.classList.add('sort-active');
                
                // Re-append sorted items
                items.forEach(item => container.appendChild(item));
            });
        });
    },

    /**
     * Initialize theme toggle
     */
    initThemeToggle: function() {
        const themeToggle = document.querySelector('[data-theme-toggle]');
        
        if (themeToggle) {
            themeToggle.addEventListener('click', function() {
                const html = document.documentElement;
                const isDark = html.classList.contains('dark');
                
                if (isDark) {
                    html.classList.remove('dark');
                    localStorage.setItem('theme', 'light');
                } else {
                    html.classList.add('dark');
                    localStorage.setItem('theme', 'dark');
                }
            });
        }
    }
};

// Trading specific functions
const Trading = {
    /**
     * Update price display with color coding
     */
    updatePrice: function(element, price, previousPrice) {
        element.textContent = Utils.formatCurrency(price);
        
        if (previousPrice) {
            element.classList.remove('price-up', 'price-down', 'price-neutral');
            
            if (price > previousPrice) {
                element.classList.add('price-up');
            } else if (price < previousPrice) {
                element.classList.add('price-down');
            } else {
                element.classList.add('price-neutral');
            }
        }
    },

    /**
     * Update status indicators
     */
    updateStatus: function(element, status) {
        element.classList.remove('status-success', 'status-error', 'status-pending');
        
        switch (status) {
            case 'success':
            case 'executed':
            case 'connected':
                element.classList.add('status-success');
                break;
            case 'error':
            case 'failed':
            case 'disconnected':
                element.classList.add('status-error');
                break;
            case 'pending':
            case 'connecting':
                element.classList.add('status-pending');
                break;
        }
    },

    /**
     * Format trade data for display
     */
    formatTradeData: function(trade) {
        return {
            symbol: trade.symbol,
            side: trade.side.toUpperCase(),
            quantity: trade.quantity || '--',
            price: trade.price ? Utils.formatCurrency(trade.price) : 'Market',
            status: trade.status.toUpperCase(),
            created: Utils.formatDateTime(trade.created_at)
        };
    },

    /**
     * Validate trading form
     */
    validateTradingForm: function(form) {
        const errors = Utils.validateForm(form);
        
        // Additional trading-specific validations
        const quantityField = form.querySelector('input[name="quantity"]');
        const amountField = form.querySelector('input[name="amount"]');
        
        if (quantityField && quantityField.value) {
            const quantity = parseFloat(quantityField.value);
            if (quantity <= 0) {
                errors.push('Quantity must be greater than 0');
            }
        }
        
        if (amountField && amountField.value) {
            const amount = parseFloat(amountField.value);
            if (amount <= 0) {
                errors.push('Amount must be greater than 0');
            }
        }
        
        return errors;
    }
};

// Form handlers
const Forms = {
    /**
     * Handle API credentials form
     */
    handleApiCredentialsForm: function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const errors = Utils.validateForm(form);
            if (errors.length > 0) {
                errors.forEach(error => Utils.showToast(error, 'error'));
                return;
            }
            
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = Utils.showButtonLoading(submitButton, 'Saving...');
            
            API.submitForm(form, function(data) {
                Utils.hideButtonLoading(submitButton, originalText);
                
                if (data.success) {
                    Utils.showToast('Credentials saved successfully!', 'success');
                    // Refresh page to update status indicators
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    Utils.showToast(data.message || 'Failed to save credentials', 'error');
                }
            });
        });
    },

    /**
     * Handle trading form
     */
    handleTradingForm: function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const errors = Trading.validateTradingForm(form);
            if (errors.length > 0) {
                errors.forEach(error => Utils.showToast(error, 'error'));
                return;
            }
            
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = Utils.showButtonLoading(submitButton, 'Executing Trade...');
            
            API.submitForm(form, function(data) {
                Utils.hideButtonLoading(submitButton, originalText);
                
                if (data.success) {
                    Utils.showToast('Trade executed successfully!', 'success');
                    form.reset();
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    Utils.showToast(data.message || 'Trade execution failed', 'error');
                }
            });
        });
    },

    /**
     * Handle password change form
     */
    handlePasswordForm: function(form) {
        form.addEventListener('submit', function(e) {
            const newPassword = form.querySelector('input[name="new_password"]').value;
            const confirmPassword = form.querySelector('input[name="confirm_password"]').value;
            
            if (newPassword !== confirmPassword) {
                e.preventDefault();
                Utils.showToast('New passwords do not match', 'error');
                return;
            }
            
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = Utils.showButtonLoading(submitButton, 'Updating...');
            
            // Reset button state after form submission
            setTimeout(() => {
                Utils.hideButtonLoading(submitButton, originalText);
            }, 1000);
        });
    }
};

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Feather icons
    feather.replace();
    
    // Initialize UI components
    UI.initTooltips();
    UI.initModals();
    UI.initDropdowns();
    UI.initTabs();
    UI.initSearch();
    UI.initSorting();
    UI.initThemeToggle();
    
    // Initialize forms
    const apiCredentialsForms = document.querySelectorAll('form[action*="api-settings"]');
    apiCredentialsForms.forEach(form => Forms.handleApiCredentialsForm(form));
    
    const tradingForms = document.querySelectorAll('form[action*="natural-trade"]');
    tradingForms.forEach(form => Forms.handleTradingForm(form));
    
    const passwordForms = document.querySelectorAll('form[action*="change-password"]');
    passwordForms.forEach(form => Forms.handlePasswordForm(form));
    
    // Initialize real-time updates
    if (typeof WebSocket !== 'undefined') {
        // WebSocket connection for real-time updates would go here
        // This is commented out as it requires server-side WebSocket implementation
    }
    
    // Initialize keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Global keyboard shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch (e.key) {
                case 'k':
                    e.preventDefault();
                    // Focus search input if exists
                    const searchInput = document.querySelector('input[type="search"]');
                    if (searchInput) searchInput.focus();
                    break;
                case '/':
                    e.preventDefault();
                    // Focus first search input
                    const firstSearch = document.querySelector('[data-search]');
                    if (firstSearch) firstSearch.focus();
                    break;
            }
        }
    });
    
    // Auto-hide flash messages with fade effect
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            alert.style.transition = 'opacity 0.5s ease-out';
            alert.style.opacity = '0';
            setTimeout(function() {
                if (alert.parentElement) {
                    alert.remove();
                }
            }, 500);
        });
    }, 5000);
    
    // Initialize price formatting for existing elements
    const priceElements = document.querySelectorAll('[data-price]');
    priceElements.forEach(element => {
        const price = parseFloat(element.dataset.price);
        if (!isNaN(price)) {
            element.textContent = Utils.formatCurrency(price);
        }
    });
    
    // Initialize percentage formatting
    const percentageElements = document.querySelectorAll('[data-percentage]');
    percentageElements.forEach(element => {
        const percentage = parseFloat(element.dataset.percentage);
        if (!isNaN(percentage)) {
            element.textContent = Utils.formatPercentage(percentage);
        }
    });
    
    // Initialize status indicators
    const statusElements = document.querySelectorAll('[data-status]');
    statusElements.forEach(element => {
        const status = element.dataset.status;
        Trading.updateStatus(element, status);
    });
    
    // Console welcome message
    console.log('%c🚀 Arbion AI Trading Platform', 'color: #1652f0; font-size: 16px; font-weight: bold;');
    console.log('%cPlatform loaded successfully!', 'color: #05d9a1; font-size: 14px;');
});

// Export for use in other scripts
window.Arbion = {
    Utils,
    API,
    UI,
    Trading,
    Forms,
    Config: ArbionConfig
};
