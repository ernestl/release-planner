/**
 * filters.js - Filter Management Module
 * 
 * Responsibilities:
 * - Filter dialog display
 * - Filter state management
 * - Timeline element visibility
 * - Filter button UI updates
 */

(function() {
    'use strict';
    
    /**
     * Apply current filters to timeline elements
     */
    function applyFilters() {
        const state = window.ReleasePlanner.state;
        const svg = window.ReleasePlanner.getSvgElement();
        
        if (!svg) {
            console.warn('SVG element not found for filtering');
            return;
        }
        
        // Hide/show lanes based on filters
        const laneTypes = ['release', 'deadline', 'holiday', 'sprint'];
        
        laneTypes.forEach(type => {
            const elements = svg.querySelectorAll(`.${type}`);
            elements.forEach(el => {
                el.style.display = state.activeFilters[type + 's'] ? '' : 'none';
            });
        });
    }
    
    /**
     * Update filter button display to show current state
     */
    function updateFilterDisplay() {
        const state = window.ReleasePlanner.state;
        const filterBtn = document.getElementById('filterBtn');
        
        if (!filterBtn) {
            return;
        }
        
        const activeCount = Object.values(state.activeFilters).filter(v => v).length;
        const totalCount = Object.keys(state.activeFilters).length;
        
        if (activeCount === totalCount) {
            filterBtn.innerHTML = '<span>Filter</span>';
        } else {
            filterBtn.innerHTML = `<span>Filter (${activeCount}/${totalCount})</span>`;
        }
    }
    
    /**
     * Style and position filter dialog
     * @param {HTMLElement} dialog - Dialog element
     */
    function styleDialog(dialog) {
        dialog.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
        `;
        
        const content = dialog.querySelector('.dialog-content');
        content.style.cssText = `
            background: white;
            padding: var(--spacing-xl);
            border-radius: var(--radius-lg);
            max-width: 400px;
            width: 90%;
            box-shadow: var(--shadow-xl);
        `;
    }
    
    /**
     * Setup event listeners for filter dialog
     * @param {HTMLElement} dialog - Dialog element
     */
    function setupDialogEvents(dialog) {
        const state = window.ReleasePlanner.state;
        
        // Cancel button
        document.getElementById('cancelFilter').addEventListener('click', function() {
            document.body.removeChild(dialog);
        });
        
        // Apply button
        document.getElementById('applyFilter').addEventListener('click', function() {
            // Update filter states from checkboxes
            const checkboxes = dialog.querySelectorAll('input[type="checkbox"]');
            checkboxes.forEach(checkbox => {
                const type = checkbox.dataset.type;
                state.activeFilters[type] = checkbox.checked;
            });
            
            applyFilters();
            updateFilterDisplay();
            document.body.removeChild(dialog);
        });
        
        // Close dialog when clicking outside
        dialog.addEventListener('click', function(e) {
            if (e.target === dialog) {
                document.body.removeChild(dialog);
            }
        });
    }
    
    /**
     * Show the filter dialog
     */
    function showFilterDialog() {
        const state = window.ReleasePlanner.state;
        
        // Create dialog
        const dialog = document.createElement('div');
        dialog.className = 'filter-dialog';
        dialog.innerHTML = `
            <div class="dialog-content">
                <h3>Filter Timeline</h3>
                <div class="filter-options">
                    ${Object.entries(state.activeFilters).map(([type, isActive]) => `
                        <label class="filter-option">
                            <input type="checkbox" data-type="${type}" ${isActive ? 'checked' : ''}>
                            <span>Show ${type.charAt(0).toUpperCase() + type.slice(1)}</span>
                        </label>
                    `).join('')}
                </div>
                <div class="dialog-actions">
                    <button class="btn btn-outline" id="cancelFilter">Cancel</button>
                    <button class="btn btn-primary" id="applyFilter">Apply</button>
                </div>
            </div>
        `;
        
        // Style and position dialog
        styleDialog(dialog);
        
        document.body.appendChild(dialog);
        
        // Setup event listeners
        setupDialogEvents(dialog);
    }
    
    /**
     * Initialize filter functionality
     */
    function init() {
        const filterBtn = document.getElementById('filterBtn');
        
        if (!filterBtn) {
            return;
        }
        
        console.log('Initializing filter functionality');
        
        // Setup filter button click
        filterBtn.addEventListener('click', showFilterDialog);
        
        // Set initial display
        updateFilterDisplay();
    }
    
    // Export public API
    window.ReleasePlanner.filters = {
        init: init,
        showDialog: showFilterDialog,
        apply: applyFilters,
        updateDisplay: updateFilterDisplay
    };
    
    console.log('filters.js loaded');
})();