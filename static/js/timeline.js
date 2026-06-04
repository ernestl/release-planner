/**
 * timeline.js - Timeline Interactions Module
 * 
 * Responsibilities:
 * - Hover tooltips
 * - Click events on timeline items
 * - Pan/drag functionality
 * - Timeline-specific UI updates
 */

(function() {
    'use strict';
    
    // Private variables
    let isDragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let dragScrollLeft = 0;
    let dragScrollTop = 0;
    let dragVelocityX = 0;
    let dragVelocityY = 0;
    let dragLastX = 0;
    let dragLastTime = 0;
    
    /**
     * Show tooltip at cursor position
     * @param {MouseEvent} event - Mouse event
     * @param {string} content - Tooltip content
     */
    function showTooltip(event, content) {
        const tooltip = window.ReleasePlanner.getTooltipElement();
        if (!tooltip) return;
        
        tooltip.innerHTML = formatTooltipContent(content);
        tooltip.classList.add('visible');
        positionTooltip(event);
    }
    
    /**
     * Position tooltip relative to cursor
     * @param {MouseEvent} event - Mouse event
     */
    function positionTooltip(event) {
        const tooltip = window.ReleasePlanner.getTooltipElement();
        const wrapper = window.ReleasePlanner.getTimelineWrapper();
        
        if (!tooltip || !wrapper) return;
        
        // Position tooltip relative to cursor
        const x = event.pageX - wrapper.offsetLeft + 10;
        const y = event.pageY - wrapper.offsetTop + 10;
        
        // Keep tooltip within bounds
        const maxX = wrapper.clientWidth - tooltip.offsetWidth - 20;
        const maxY = wrapper.clientHeight - tooltip.offsetHeight - 20;
        
        tooltip.style.left = Math.min(x, maxX) + 'px';
        tooltip.style.top = Math.min(y, maxY) + 'px';
    }
    
    /**
     * Hide the tooltip
     */
    function hideTooltip() {
        const tooltip = window.ReleasePlanner.getTooltipElement();
        if (!tooltip) return;
        
        tooltip.classList.remove('visible');
        tooltip.innerHTML = '';
    }
    
    /**
     * Format tooltip content nicely
     * @param {string} content - Raw tooltip content
     * @returns {string} Formatted HTML
     */
    function formatTooltipContent(content) {
        // Parse content and format it nicely
        const parts = content.split(': ');
        if (parts.length >= 2) {
            const header = parts[0];
            const details = parts.slice(1).join(': ');
            
            // Check if it's a date range
            if (details.includes(' to ')) {
                const [start, end] = details.split(' to ');
                return `
                    <div class="tooltip-header">${header}</div>
                    <div class="tooltip-dates">${formatDate(start)} → ${formatDate(end)}</div>
                `;
            } else {
                return `
                    <div class="tooltip-header">${header}</div>
                    <div class="tooltip-description">${details}</div>
                `;
            }
        }
        
        return `<div class="tooltip-description">${content}</div>`;
    }
    
    /**
     * Format date string for display
     * @param {string} dateStr - Date string
     * @returns {string} Formatted date
     */
    function formatDate(dateStr) {
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        } catch (e) {
            return dateStr;
        }
    }
    
    /**
     * Setup hover event listeners for timeline items
     * @param {SVGSVGElement} svg - Timeline SVG element
     */
    function setupHoverEvents(svg) {
        svg.addEventListener('mouseover', function(e) {
            const target = e.target;
            // Check if target is an SVG element we care about
            const isTimelineElement = target.tagName === 'polygon' || 
                                     target.tagName === 'rect' ||
                                     (target.classList && 
                                      (target.classList.contains('milestone-deadline') || 
                                       target.classList.contains('item')));
            
            if (isTimelineElement) {
                const title = target.querySelector('title');
                if (title && title.textContent) {
                    showTooltip(e, title.textContent);
                }
            }
        });
        
        svg.addEventListener('mousemove', function(e) {
            const tooltip = window.ReleasePlanner.getTooltipElement();
            if (tooltip && tooltip.classList.contains('visible')) {
                positionTooltip(e);
            }
        });
        
        svg.addEventListener('mouseout', function(e) {
            const target = e.target;
            const isTimelineElement = target.tagName === 'polygon' || 
                                     target.tagName === 'rect' ||
                                     (target.classList && 
                                      (target.classList.contains('milestone-deadline') || 
                                       target.classList.contains('item')));
            
            if (isTimelineElement) {
                hideTooltip();
            }
        });
    }
    
    /**
     * Setup click events for timeline items
     * @param {SVGSVGElement} svg - Timeline SVG element
     */
    function setupClickEvents(svg) {
        svg.addEventListener('click', function(e) {
            const target = e.target;
            if (target.classList && target.classList.contains('milestone-deadline')) {
                const title = target.querySelector('title');
                if (title) {
                    alert(`Deadline: ${title.textContent}\n\nClick the diamond to see details.`);
                }
            }
        });
    }
    
    /**
     * Setup pan/drag events for timeline
     * @param {SVGSVGElement} svg - Timeline SVG element
     */
    function setupPanEvents(svg) {
        const wrapper = svg.parentElement;
        const state = window.ReleasePlanner.state;
        
        // Enable panning on mouse down
        svg.addEventListener('mousedown', function(e) {
            if (!state.isPanEnabled) return;
            
            isDragging = true;
            dragStartX = e.pageX - wrapper.offsetLeft;
            dragStartY = e.pageY - wrapper.offsetTop;
            dragScrollLeft = wrapper.scrollLeft;
            dragScrollTop = wrapper.scrollTop;
            
            // Add dragging style
            wrapper.style.cursor = 'grabbing';
            svg.style.cursor = 'grabbing';
            
            // Record initial values for velocity calculation
            dragLastX = e.pageX;
            dragLastTime = Date.now();
        });
        
        // Handle mouse move for dragging
        document.addEventListener('mousemove', function(e) {
            if (!isDragging || !state.isPanEnabled) return;
            
            e.preventDefault();
            
            const x = e.pageX - wrapper.offsetLeft;
            const y = e.pageY - wrapper.offsetTop;
            
            const walkX = (x - dragStartX) * 2; // Multiply for smoother dragging
            const walkY = (y - dragStartY) * 2;
            
            wrapper.scrollLeft = dragScrollLeft - walkX;
            wrapper.scrollTop = dragScrollTop - walkY;
            
            // Calculate velocity for momentum scrolling
            const currentTime = Date.now();
            const deltaTime = currentTime - dragLastTime;
            
            if (deltaTime > 0) {
                const deltaX = e.pageX - dragLastX;
                dragVelocityX = deltaX / deltaTime;
                dragLastX = e.pageX;
                dragLastTime = currentTime;
            }
        });
        
        // Handle mouse up to stop dragging
        document.addEventListener('mouseup', function() {
            if (!isDragging) return;
            
            isDragging = false;
            
            // Restore cursor
            wrapper.style.cursor = '';
            svg.style.cursor = '';
            
            // Apply momentum scrolling
            if (Math.abs(dragVelocityX) > 0.1) {
                applyMomentumScrolling(wrapper);
            }
        });
    }
    
    /**
     * Apply momentum scrolling after drag ends
     * @param {HTMLElement} wrapper - Timeline wrapper element
     */
    function applyMomentumScrolling(wrapper) {
        let currentScroll = wrapper.scrollLeft;
        const direction = dragVelocityX > 0 ? 1 : -1;
        let currentVelocity = dragVelocityX;
        
        const momentumAnimation = setInterval(function() {
            currentScroll += currentVelocity * 100;
            wrapper.scrollLeft = currentScroll;
            
            // Slow down velocity
            currentVelocity *= 0.95;
            
            // Stop when velocity is too low
            if (Math.abs(currentVelocity) < 0.01) {
                clearInterval(momentumAnimation);
            }
        }, 16);
    }
    
    /**
     * Initialize timeline interactions
     */
    function init() {
        const svg = window.ReleasePlanner.getSvgElement();
        const tooltip = window.ReleasePlanner.getTooltipElement();
        
        if (!svg) {
            console.warn('Timeline SVG not found');
            return;
        }
        
        if (!tooltip) {
            console.warn('Tooltip element not found');
            return;
        }
        
        console.log('Initializing timeline interactions');
        
        setupHoverEvents(svg);
        setupClickEvents(svg);
        setupPanEvents(svg);
    }
    
    // Export public API
    window.ReleasePlanner.timeline = {
        init: init,
        showTooltip: showTooltip,
        hideTooltip: hideTooltip,
        positionTooltip: positionTooltip
    };
    
    console.log('timeline.js loaded');
})();