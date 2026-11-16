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
    isPanEnabled: false,
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
                    <span>Export configuration (JSON)</span>
                </button>
            </div>
        </div>
    `;

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

    const exportBtn = document.getElementById('exportBtn');
    const rect = exportBtn.getBoundingClientRect();
    menu.style.top = rect.bottom + 'px';
    menu.style.right = (window.innerWidth - rect.right) + 'px';

    document.body.appendChild(menu);

    const removeMenu = () => {
        if (menu.parentNode) {
            menu.parentNode.removeChild(menu);
        }
    };

    menu.querySelectorAll('.export-option').forEach(option => {
        option.addEventListener('click', function(event) {
            event.stopPropagation();
            const format = this.dataset.format;
            removeMenu();
            Promise.resolve(exportTimeline(format)).catch(function(error) {
                alert(error && error.message ? error.message : 'Export failed.');
            });
        });
    });

    setTimeout(() => {
        const closeMenu = (event) => {
            if (!menu.contains(event.target) && event.target !== exportBtn) {
                removeMenu();
                document.removeEventListener('click', closeMenu);
            }
        };
        document.addEventListener('click', closeMenu);
    }, 0);
}

function exportTimeline(format) {
    switch (format) {
        case 'svg':
            return exportAsSVG();
        case 'png':
            return exportAsPNG();
        case 'pdf':
            return exportAsPDF();
        case 'json':
            return exportAsJSON();
        default:
            throw new Error('Unknown export format.');
    }
}

function exportBaseName() {
    const source = planSource();
    const project = String(source.project || 'release').trim() || 'release';
    const cycle = String(source.cycle || '').trim();
    return cycle ? `${project}-${cycle}-release-plan` : `${project}-release-plan`;
}

function planSource() {
    const element = document.getElementById('plan-source');
    if (!element) {
        throw new Error('Plan configuration is missing.');
    }
    return JSON.parse(element.textContent);
}

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function() {
        URL.revokeObjectURL(url);
    }, 0);
}

function timelineSvgMarkup() {
    const svg = document.getElementById('timelineSvg');
    if (!svg) {
        throw new Error('Timeline is missing.');
    }
    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return {
        markup: new XMLSerializer().serializeToString(clone),
        width: Number(svg.getAttribute('width')),
        height: Number(svg.getAttribute('height')),
    };
}

function exportAsSVG() {
    const timeline = timelineSvgMarkup();
    const blob = new Blob([timeline.markup], { type: 'image/svg+xml' });
    downloadBlob(blob, `${exportBaseName()}.svg`);
}

function rasterizeTimeline(scale) {
    const timeline = timelineSvgMarkup();
    const url = URL.createObjectURL(new Blob([timeline.markup], { type: 'image/svg+xml;charset=utf-8' }));
    return new Promise(function(resolve, reject) {
        const image = new Image();
        image.onload = function() {
            const canvas = document.createElement('canvas');
            canvas.width = Math.round(timeline.width * scale);
            canvas.height = Math.round(timeline.height * scale);
            const context = canvas.getContext('2d');
            context.fillStyle = '#ffffff';
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            URL.revokeObjectURL(url);
            resolve({ canvas: canvas, width: timeline.width, height: timeline.height });
        };
        image.onerror = function() {
            URL.revokeObjectURL(url);
            reject(new Error('Could not draw the timeline.'));
        };
        image.src = url;
    });
}

function exportAsPNG() {
    return rasterizeTimeline(2).then(function(raster) {
        return new Promise(function(resolve, reject) {
            raster.canvas.toBlob(function(blob) {
                if (!blob) {
                    reject(new Error('Could not create the PNG.'));
                    return;
                }
                downloadBlob(blob, `${exportBaseName()}.png`);
                resolve();
            }, 'image/png');
        });
    });
}

function exportAsPDF() {
    return rasterizeTimeline(2).then(function(raster) {
        return new Promise(function(resolve, reject) {
            raster.canvas.toBlob(function(blob) {
                if (!blob) {
                    reject(new Error('Could not create the PDF image.'));
                    return;
                }
                blob.arrayBuffer().then(function(buffer) {
                    const pdf = buildPdf(
                        new Uint8Array(buffer),
                        raster.canvas.width,
                        raster.canvas.height,
                        raster.width,
                        raster.height
                    );
                    downloadBlob(new Blob([pdf], { type: 'application/pdf' }), `${exportBaseName()}.pdf`);
                    resolve();
                }).catch(reject);
            }, 'image/jpeg', 0.92);
        });
    });
}

function exportAsJSON() {
    const blob = new Blob(
        [JSON.stringify(planSource(), null, 2) + '\n'],
        { type: 'application/json' }
    );
    downloadBlob(blob, `${exportBaseName()}.json`);
}

function concatBytes(parts) {
    const size = parts.reduce(function(total, part) {
        return total + part.length;
    }, 0);
    const out = new Uint8Array(size);
    let position = 0;
    parts.forEach(function(part) {
        out.set(part, position);
        position += part.length;
    });
    return out;
}

function buildPdf(jpegBytes, imageWidth, imageHeight, pageWidth, pageHeight) {
    const encoder = new TextEncoder();
    const content = encoder.encode(`q\n${pageWidth} 0 0 ${pageHeight} 0 0 cm\n/Im1 Do\nQ\n`);
    const objects = [
        encoder.encode('<< /Type /Catalog /Pages 2 0 R >>'),
        encoder.encode('<< /Type /Pages /Kids [3 0 R] /Count 1 >>'),
        encoder.encode(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageWidth} ${pageHeight}] /Contents 4 0 R /Resources << /XObject << /Im1 5 0 R >> >> >>`),
        concatBytes([
            encoder.encode(`<< /Length ${content.length} >>\nstream\n`),
            content,
            encoder.encode('\nendstream'),
        ]),
        concatBytes([
            encoder.encode(`<< /Type /XObject /Subtype /Image /Width ${imageWidth} /Height ${imageHeight} /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpegBytes.length} >>\nstream\n`),
            jpegBytes,
            encoder.encode('\nendstream'),
        ]),
    ];

    const chunks = [encoder.encode('%PDF-1.4\n')];
    let offset = chunks[0].length;
    const xref = [0];
    objects.forEach(function(body, index) {
        const number = index + 1;
        const head = encoder.encode(`${number} 0 obj\n`);
        const tail = encoder.encode('\nendobj\n');
        xref[number] = offset;
        chunks.push(head, body, tail);
        offset += head.length + body.length + tail.length;
    });

    let xrefTable = `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
    for (let number = 1; number <= objects.length; number += 1) {
        xrefTable += `${String(xref[number]).padStart(10, '0')} 00000 n \n`;
    }
    xrefTable += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${offset}\n%%EOF\n`;
    chunks.push(encoder.encode(xrefTable));
    return concatBytes(chunks);
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