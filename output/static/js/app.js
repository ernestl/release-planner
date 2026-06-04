/**
 * app.js - Release Planner Core
 * 
 * Responsibilities:
 * - Application state management
 * - Plan data loading
 * - Module coordination
 * - Core features (fullscreen, export, sidebar)
 * - Keyboard shortcuts
 */

// Application state
const AppState = {
    currentZoom: '6m',
    activeFilters: {
        releases: true,
        deadlines: true,
        holidays: true,
        sprints: true
    },
    isFullscreen: false,
    planData: null,
    isPanEnabled: true,
    hoveredElement: null
};

// Expose state and core functions globally
window.ReleasePlanner = {
    // Application state
    state: AppState,
    
    // Utility functions for modules
    getTooltipElement: () => document.getElementById('timelineTooltip'),
    getSvgElement: () => document.getElementById('timelineSvg'),
    getTimelineWrapper: () => document.querySelector('.timeline-wrapper'),
    
    // Module registration slots
    timeline: null,
    zoom: null,
    filters: null,
    
    // Core functions
    _coreFunctions: {}
};

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    // Load plan data from JSON script tag
    const planDataElement = document.getElementById('plan-data');
    if (planDataElement) {
        AppState.planData = JSON.parse(planDataElement.textContent);
        console.log('Plan data loaded');
    } else {
        console.error('Plan data element not found');
    }
    
    // Initialize all registered modules
    if (window.ReleasePlanner.timeline && window.ReleasePlanner.timeline.init) {
        window.ReleasePlanner.timeline.init();
    }
    
    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.init) {
        window.ReleasePlanner.zoom.init();
    }
    
    if (window.ReleasePlanner.filters && window.ReleasePlanner.filters.init) {
        window.ReleasePlanner.filters.init();
    }
    
    // Initialize core features
    initFullscreen();
    initSidebarToggle();
    initExport();
    setupKeyboardShortcuts();
    
    // Quick inline script to hide loading overlay
    window.addEventListener('load', function() {
        setTimeout(function() {
            const loadingOverlay = document.getElementById('loadingOverlay');
            if (loadingOverlay) {
                loadingOverlay.classList.add('fade-out');
                setTimeout(function() {
                    loadingOverlay.style.display = 'none';
                }, 300);
            }
        }, 500);
    });
    
    console.log('Release Planner application initialized');
});

// Initialize fullscreen functionality
function initFullscreen() {
    const fullscreenBtn = document.getElementById('fullscreenBtn');
    const exitFullscreenBtn = document.querySelector('.exit-fullscreen-btn');
    
    if (fullscreenBtn) {
        fullscreenBtn.addEventListener('click', toggleFullscreen);
    }
    
    if (exitFullscreenBtn) {
        exitFullscreenBtn.addEventListener('click', exitFullscreen);
    }
    
    // Listen for Escape key to exit fullscreen
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && AppState.isFullscreen) {
            exitFullscreen();
        }
    });
    
    // Listen for fullscreen change events
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);
}

function toggleFullscreen() {
    if (!AppState.isFullscreen) {
        enterFullscreen();
    } else {
        exitFullscreen();
    }
}

function enterFullscreen() {
    const element = document.documentElement;
    
    if (element.requestFullscreen) {
        element.requestFullscreen();
    } else if (element.webkitRequestFullscreen) {
        element.webkitRequestFullscreen();
    } else if (element.mozRequestFullScreen) {
        element.mozRequestFullScreen();
    } else if (element.msRequestFullscreen) {
        element.msRequestFullscreen();
    }
    
    AppState.isFullscreen = true;
    document.body.classList.add('fullscreen-mode');
}

function exitFullscreen() {
    if (document.exitFullscreen) {
        document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
    } else if (document.mozCancelFullScreen) {
        document.mozCancelFullScreen();
    } else if (document.msExitFullscreen) {
        document.msExitFullscreen();
    }
    
    AppState.isFullscreen = false;
    document.body.classList.remove('fullscreen-mode');
}

function handleFullscreenChange() {
    AppState.isFullscreen = !!(document.fullscreenElement || 
                               document.webkitFullscreenElement || 
                               document.mozFullScreenElement || 
                               document.msFullscreenElement);
    
    document.body.classList.toggle('fullscreen-mode', AppState.isFullscreen);
}

// Initialize sidebar toggle for mobile
function initSidebarToggle() {
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('open');
            toggleBtn.classList.toggle('open');
            toggleBtn.innerHTML = sidebar.classList.contains('open') ? '✕' : '☰';
        });
    }
}

// Initialize export functionality
function initExport() {
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
        exportBtn.addEventListener('click', showExportMenu);
    }
}

function showExportMenu() {
    // Create export menu
    const menu = document.createElement('div');
    menu.className = 'export-menu';
    menu.innerHTML = `
        <div class="menu-content">
            <h3>Export Timeline</h3>
            <div class="export-options">
                <button class="export-option" data-format="svg">
                    <span>Export as SVG</span>
                </button>
                <button class="export-option" data-format="png">
                    <span>Export as PNG</span>
                </button>
                <button class="export-option" data-format="pdf">
                    <span>Export as PDF</span>
                </button>
                <button class="export-option" data-format="json">
                    <span>Export Data (JSON)</span>
                </button>
            </div>
        </div>
    `;
    
    // Style the menu
    menu.style.cssText = `
        position: absolute;
        background: white;
        border: 1px solid var(--color-border);
        border-radius: var(--radius-md);
        box-shadow: var(--shadow-lg);
        min-width: 200px;
        z-index: 1000;
    `;
    
    const content = menu.querySelector('.menu-content');
    content.style.cssText = `
        padding: var(--spacing-md);
    `;
    
    // Position the menu near the export button
    const exportBtn = document.getElementById('exportBtn');
    const rect = exportBtn.getBoundingClientRect();
    menu.style.top = rect.bottom + 'px';
    menu.style.right = (window.innerWidth - rect.right) + 'px';
    
    document.body.appendChild(menu);
    
    // Setup event listeners for export options
    menu.querySelectorAll('.export-option').forEach(option => {
        option.addEventListener('click', function() {
            const format = this.dataset.format;
            exportTimeline(format);
            document.body.removeChild(menu);
        });
    });
    
    // Close menu when clicking outside
    setTimeout(() => {
        const closeMenu = (e) => {
            if (!menu.contains(e.target) && e.target !== exportBtn) {
                document.body.removeChild(menu);
                document.removeEventListener('click', closeMenu);
            }
        };
        document.addEventListener('click', closeMenu);
    }, 0);
}

function exportTimeline(format) {
    switch (format) {
        case 'svg':
            exportAsSVG();
            break;
        case 'png':
            exportAsPNG();
            break;
        case 'pdf':
            exportAsPDF();
            break;
        case 'json':
            exportAsJSON();
            break;
    }
}

function exportAsSVG() {
    alert('SVG export would be implemented here\nCurrent SVG is already available at output/plan.svg');
}

function exportAsPNG() {
    alert('PNG export would require html2canvas or similar library');
}

function exportAsPDF() {
    alert('PDF export would require jsPDF or similar library');
}

function exportAsJSON() {
    const dataStr = JSON.stringify(AppState.planData, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `release-plan-${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // Zoom shortcuts
        if (e.ctrlKey || e.metaKey) {
            switch (e.key) {
                case '=':
                case '+':
                    e.preventDefault();
                    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.zoomIn) {
                        window.ReleasePlanner.zoom.zoomIn();
                    }
                    break;
                case '-':
                    e.preventDefault();
                    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.zoomOut) {
                        window.ReleasePlanner.zoom.zoomOut();
                    }
                    break;
                case '0':
                    e.preventDefault();
                    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.setZoomLevel) {
                        window.ReleasePlanner.zoom.setZoomLevel('fit');
                    }
                    break;
            }
        }
        
        // Pan with arrow keys
        if (e.key.startsWith('Arrow')) {
            const wrapper = document.querySelector('.timeline-wrapper');
            if (!wrapper) return;
            
            const scrollAmount = 50;
            switch (e.key) {
                case 'ArrowLeft':
                    wrapper.scrollLeft -= scrollAmount;
                    break;
                case 'ArrowRight':
                    wrapper.scrollLeft += scrollAmount;
                    break;
                case 'ArrowUp':
                    wrapper.scrollTop -= scrollAmount;
                    break;
                case 'ArrowDown':
                    wrapper.scrollTop += scrollAmount;
                    break;
            }
        }
    });
    
    // Wheel zoom
    const timelineWrapper = document.querySelector('.timeline-wrapper');
    if (timelineWrapper) {
        timelineWrapper.addEventListener('wheel', function(e) {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault();
                if (e.deltaY < 0) {
                    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.zoomIn) {
                        window.ReleasePlanner.zoom.zoomIn();
                    }
                } else {
                    if (window.ReleasePlanner.zoom && window.ReleasePlanner.zoom.zoomOut) {
                        window.ReleasePlanner.zoom.zoomOut();
                    }
                }
            }
        });
    }
}

// Utility functions
window.ReleasePlanner.utils = {
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
    
    throttle: function(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

console.log('app.js loaded');