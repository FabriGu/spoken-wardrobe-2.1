/**
 * GridManager - Dynamic Era Grid Layout
 *
 * Manages the growing grid of era cells, handling layout transitions,
 * cell creation, and zoom-out animations.
 */

import config from '../config.js';

export class GridManager {
    constructor(containerId = 'era-grid', configOverrides = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            throw new Error(`Grid container #${containerId} not found`);
        }

        this.config = { ...config, ...configOverrides };
        this.cells = new Map(); // era id -> { element, canvas, ctx }
        this.currentLayout = null;
        this.visibleEras = 0;

        // Callbacks
        this.onCellCreated = null;
        this.onLayoutChanged = null;

        console.log('[GridManager] Initialized');
    }

    /**
     * Get the appropriate layout for a given number of eras
     */
    _getLayoutForEras(numEras) {
        const progressions = this.config.gridProgression;
        for (let i = progressions.length - 1; i >= 0; i--) {
            if (numEras >= progressions[i].eras) {
                return progressions[i];
            }
        }
        return progressions[0];
    }

    /**
     * Create a single era cell
     */
    _createCell(era) {
        const cell = document.createElement('div');
        cell.className = 'era-cell';
        cell.dataset.era = era.id;

        // Create canvas for effect rendering
        const canvas = document.createElement('canvas');
        canvas.width = this.config.cellResolution.w;
        canvas.height = this.config.cellResolution.h;
        cell.appendChild(canvas);

        // Create label overlay (hidden by default, shown briefly on new cell)
        const label = document.createElement('div');
        label.className = 'cell-label';
        label.innerHTML = `
            <span class="era-year">${era.year}</span>
            <span class="era-name">${era.name}</span>
        `;
        cell.appendChild(label);

        // Store reference
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        this.cells.set(era.id, { element: cell, canvas, ctx, era });

        // Show label briefly then hide
        cell.classList.add('show-label');
        setTimeout(() => {
            cell.classList.remove('show-label');
        }, 3000);

        return { element: cell, canvas, ctx };
    }

    /**
     * Update the grid layout based on current era count
     */
    _updateLayout(numEras) {
        const layout = this._getLayoutForEras(numEras);
        const layoutClass = `grid-${layout.cols}x${layout.rows}`;

        if (this.currentLayout !== layoutClass) {
            // Remove old layout class
            if (this.currentLayout) {
                this.container.classList.remove(this.currentLayout);
            }

            // Add new layout class
            this.container.classList.add(layoutClass);
            this.currentLayout = layoutClass;

            console.log(`[GridManager] Layout changed to ${layoutClass}`);

            if (this.onLayoutChanged) {
                this.onLayoutChanged(layout);
            }
        }
    }

    /**
     * Show a single era (add to grid if new)
     */
    showEra(eraId) {
        const eraConfig = this.config.eras.find(e => e.id === eraId);
        if (!eraConfig) {
            console.warn(`[GridManager] Era ${eraId} not found in config`);
            return null;
        }

        // Check if already exists
        if (this.cells.has(eraId)) {
            return this.cells.get(eraId);
        }

        // Create the cell
        const cellData = this._createCell(eraConfig);

        // Add to container
        this.container.appendChild(cellData.element);
        this.visibleEras++;

        // Update layout
        this._updateLayout(this.visibleEras);

        // Show global era label briefly
        this._showEraLabel(eraConfig);

        console.log(`[GridManager] Added era ${eraId}: ${eraConfig.name}`);

        if (this.onCellCreated) {
            this.onCellCreated(eraId, cellData);
        }

        return cellData;
    }

    /**
     * Show eras up to a given number
     */
    showErasUpTo(maxEraId) {
        const results = [];
        for (let i = 1; i <= maxEraId; i++) {
            if (!this.config.skipEras.includes(i)) {
                results.push(this.showEra(i));
            }
        }
        return results;
    }

    /**
     * Show global era label overlay (simple show/hide, no animation)
     */
    _showEraLabel(era) {
        const label = document.getElementById('era-label');
        if (!label) return;

        label.querySelector('.era-year').textContent = era.year;
        label.querySelector('.era-name').textContent = era.name;

        // Simple show/hide
        label.classList.remove('hidden');

        // Hide after 2.5 seconds
        setTimeout(() => {
            label.classList.add('hidden');
        }, 2500);
    }

    /**
     * Get canvas for a specific era
     */
    getCanvas(eraId) {
        const cell = this.cells.get(eraId);
        return cell ? cell.canvas : null;
    }

    /**
     * Get context for a specific era
     */
    getContext(eraId) {
        const cell = this.cells.get(eraId);
        return cell ? cell.ctx : null;
    }

    /**
     * Get all current cells
     */
    getAllCells() {
        return this.cells;
    }

    /**
     * Set "generating" state for AI cells
     */
    setGenerating(eraId, isGenerating) {
        const cell = this.cells.get(eraId);
        if (cell) {
            if (isGenerating) {
                cell.element.classList.add('generating');
            } else {
                cell.element.classList.remove('generating');
            }
        }
    }

    /**
     * Reset the grid (remove all cells)
     */
    reset() {
        // Remove all cells
        this.cells.forEach(cell => {
            cell.element.remove();
        });
        this.cells.clear();
        this.visibleEras = 0;

        // Reset layout
        if (this.currentLayout) {
            this.container.classList.remove(this.currentLayout);
            this.currentLayout = null;
        }

        console.log('[GridManager] Reset');
    }

    /**
     * Get number of visible eras
     */
    getVisibleEraCount() {
        return this.visibleEras;
    }

    /**
     * Check if all eras are visible
     */
    isComplete() {
        const totalActive = this.config.totalEras - this.config.skipEras.length;
        return this.visibleEras >= totalActive;
    }
}
