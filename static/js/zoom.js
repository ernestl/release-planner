/**
 * zoom.js - Zoom Control Module
 * 
 * Responsibilities:
 * - Zoom level management
 * - Zoom button UI updates
 * - Zoom in/out functions
 * - Future: Viewport adjustment
 */

(function() {
    'use strict';
    
    /**
     * Set the current zoom level
     * @param {string} zoomLevel - Zoom level (fit, 3m, 6m, 12m, all)
     */
    function setZoomLevel(zoomLevel) {
        const state = window.ReleasePlanner.state;
        state.currentZoom = zoomLevel;
        
        updateZoomControls();
        
        // Future: Actually adjust timeline viewport
        // using the zoom data from state.planData.zoomLevels
        console.log(`Zoom level changed to: ${zoomLevel}`);
    }
    
    /**
     * Update zoom control UI to reflect current state
     */
    function updateZoomControls() {
        const state = window.ReleasePlanner.state;
        const activeButton = document.querySelector(
            `.zoom-btn[data-zoom="${state.currentZoom}"]`
        );
        
        if (activeButton) {
            document.querySelectorAll('.zoom-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            activeButton.classList.add('active');
        }
    }
    
    /**
     * Zoom in (move to next higher zoom level)
     */
    function zoomIn() {
        const state = window.ReleasePlanner.state;
        const zoomLevels = ['all', '12m', '6m', '3m', 'fit'];
        const currentIndex = zoomLevels.indexOf(state.currentZoom);
        if (currentIndex < zoomLevels.length - 1) {
            setZoomLevel(zoomLevels[currentIndex + 1]);
        }
    }
    
    /**
     * Zoom out (move to next lower zoom level)
     */
    function zoomOut() {
        const state = window.ReleasePlanner.state;
        const zoomLevels = ['all', '12m', '6m', '3m', 'fit'];
        const currentIndex = zoomLevels.indexOf(state.currentZoom);
        if (currentIndex > 0) {
            setZoomLevel(zoomLevels[currentIndex - 1]);
        }
    }
    
    /**
     * Initialize zoom controls
     */
    function init() {
        const zoomButtons = document.querySelectorAll('.zoom-btn');
        
        if (zoomButtons.length === 0) {
            console.warn('Zoom buttons not found');
            return;
        }
        
        console.log('Initializing zoom controls');
        
        // Setup click events for zoom buttons
        zoomButtons.forEach(button => {
            button.addEventListener('click', function() {
                const zoomLevel = this.dataset.zoom;
                setZoomLevel(zoomLevel);
            });
        });
        
        // Setup pan toggle
        const panToggle = document.getElementById('panToggle');
        if (panToggle) {
            panToggle.addEventListener('change', function() {
                window.ReleasePlanner.state.isPanEnabled = this.checked;
            });
        }
        
        // Set initial state
        updateZoomControls();
    }
    
    // Export public API
    window.ReleasePlanner.zoom = {
        init: init,
        setZoomLevel: setZoomLevel,
        zoomIn: zoomIn,
        zoomOut: zoomOut,
        updateControls: updateZoomControls
    };
    
    console.log('zoom.js loaded');
})();