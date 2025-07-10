// Theme switching functionality
function switchTheme() {
    const body = document.querySelector('body');
    const isCurrentlyDark = body.style.background.includes('linear-gradient(135deg, #2c3e50');
    
    if (isCurrentlyDark) {
        body.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
    } else {
        body.style.background = 'linear-gradient(135deg, #2c3e50 0%, #34495e 100%)';
    }
}

// Form visibility and advanced filters
function toggleForm() {
    const formContainer = document.getElementById('device-form');
    const isVisible = formContainer.style.display === 'block';
    
    if (isVisible) {
        formContainer.style.display = 'none';
    } else {
        formContainer.style.display = 'block';
        formContainer.scrollIntoView({ behavior: 'smooth' });
    }
}

function toggleAdvancedFilters() {
    const advancedFilters = document.getElementById('advanced-filters');
    const toggleBtn = document.getElementById('advanced-toggle-btn');
    
    if (advancedFilters.classList.contains('show')) {
        advancedFilters.classList.remove('show');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> Show Advanced Filters';
    } else {
        advancedFilters.classList.add('show');
        toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> Hide Advanced Filters';
    }
}

// User type selection
function selectUserType(type) {
    document.querySelectorAll('.user-type-card').forEach(card => {
        card.classList.remove('active');
    });
    
    const selectedCard = document.querySelector(`[data-user-type="${type}"]`);
    if (selectedCard) {
        selectedCard.classList.add('active');
    }
    
    const useSelect = document.getElementById('use');
    if (useSelect) {
        useSelect.value = type;
    }
    
    // Auto-populate recommendations based on user type
    updateRecommendations(type);
}

function updateRecommendations(userType) {
    const recommendations = {
        'Personal': {
            'price_range_min': 400,
            'price_range_max': 1200,
            'ram': 8,
            'storage': 256
        },
        'Work': {
            'price_range_min': 800,
            'price_range_max': 2000,
            'ram': 16,
            'storage': 512
        },
        'Government': {
            'price_range_min': 1000,
            'price_range_max': 3000,
            'ram': 32,
            'storage': 1000
        }
    };

    const rec = recommendations[userType];
    if (rec) {
        const priceMin = document.getElementById('price_range_min');
        const priceMax = document.getElementById('price_range_max');
        const ram = document.getElementById('ram');
        const storage = document.getElementById('storage');
        
        if (priceMin) priceMin.value = rec.price_range_min;
        if (priceMax) priceMax.value = rec.price_range_max;
        if (ram) ram.value = rec.ram;
        if (storage) storage.value = rec.storage;
        
        updateAllRangeValues();
    }
}

// Range slider updates
function updatePriceRangeValue() {
    const minPrice = document.getElementById('price_range_min');
    const maxPrice = document.getElementById('price_range_max');
    const minDisplay = document.getElementById('price_range_min_value');
    const maxDisplay = document.getElementById('price_range_max_value');
    
    if (minPrice && maxPrice && minDisplay && maxDisplay) {
        minDisplay.textContent = minPrice.value;
        maxDisplay.textContent = maxPrice.value;
    }
}

function updateRangeValue(sliderId, displayId, suffix = '') {
    const slider = document.getElementById(sliderId);
    const display = document.getElementById(displayId);
    if (slider && display) {
        display.textContent = slider.value + suffix;
    }
}

function updateAllRangeValues() {
    updatePriceRangeValue();
    updateRangeValue('cpu_speed', 'cpu_speed_value', ' GHz');
    updateRangeValue('ram', 'ram_value', ' GB');
    updateRangeValue('storage', 'storage_value', ' GB');
    updateRangeValue('screen_size', 'screen_size_value', '"');
    updateRangeValue('cores', 'cores_value', ' cores');
    updateRangeValue('threads', 'threads_value', ' threads');
}

function checkStandards() {
    const cpuSpeed = document.getElementById('cpu_speed');
    const ram = document.getElementById('ram');
    const storage = document.getElementById('storage');
    const screenSize = document.getElementById('screen_size');

    const minCpuSpeed = 3.0;
    const minRam = 8;
    const minStorage = 256;
    const minScreenSize = 9;

    let alertMessage = '';
    if (cpuSpeed && cpuSpeed.value < minCpuSpeed) alertMessage += 'CPU Speed below recommended standards.\n';
    if (ram && ram.value < minRam) alertMessage += 'RAM below recommended standards.\n';
    if (storage && storage.value < minStorage) alertMessage += 'Storage below recommended standards.\n';
    if (screenSize && screenSize.value < minScreenSize) alertMessage += 'Screen Size below recommended standards.\n';

    if (alertMessage) alert(alertMessage);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    updateAllRangeValues();
    
    // Refresh devices functionality
    const refreshBtn = document.getElementById('refresh-devices-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
            refreshBtn.disabled = true;
            
            fetch('/refresh-devices', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert(`Successfully refreshed ${data.count} devices! Page will reload.`);
                    location.reload();
                } else {
                    alert('Error refreshing devices: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error refreshing devices. Check console for details.');
            })
            .finally(() => {
                refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i> Refresh Device Data';
                refreshBtn.disabled = false;
            });
        });
    }

    // Theme toggle
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('change', switchTheme);
    }
});
