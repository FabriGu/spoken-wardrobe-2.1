/**
 * ClothSimulator.js
 *
 * Ammo.js-based soft body cloth simulation for clothing meshes.
 * Designed to work with Three.js SkinnedMesh garments.
 */

import * as THREE from 'three';

export class ClothSimulator {
    constructor(options = {}) {
        this.enabled = false;
        this.physicsWorld = null;
        this.softBodies = new Map(); // mesh -> softBody
        this.rigidBodies = [];
        this.transformAux = null;
        this.Ammo = null;

        // Physics settings
        this.gravity = options.gravity || -9.8;
        this.margin = options.margin || 0.05;
        this.damping = options.damping || 0.01;
        this.stiffness = options.stiffness || 0.9;
        this.iterations = options.iterations || 10;

        // State
        this.initialized = false;
        this.paused = false;

        // Scene reference for adding visual meshes
        this.scene = null;
    }

    /**
     * Set the Three.js scene for adding visual meshes
     */
    setScene(scene) {
        this.scene = scene;
        console.log('[ClothSimulator] Scene set');
    }

    /**
     * Initialize Ammo.js physics world
     */
    async init() {
        if (this.initialized) return true;

        try {
            // Load Ammo.js
            if (typeof Ammo === 'undefined') {
                console.log('[ClothSimulator] Loading Ammo.js...');
                await this._loadAmmo();
            }

            this.Ammo = await Ammo();
            console.log('[ClothSimulator] Ammo.js loaded');

            // Create physics world with soft body support
            const collisionConfiguration = new this.Ammo.btSoftBodyRigidBodyCollisionConfiguration();
            const dispatcher = new this.Ammo.btCollisionDispatcher(collisionConfiguration);
            const broadphase = new this.Ammo.btDbvtBroadphase();
            const solver = new this.Ammo.btSequentialImpulseConstraintSolver();
            const softBodySolver = new this.Ammo.btDefaultSoftBodySolver();

            this.physicsWorld = new this.Ammo.btSoftRigidDynamicsWorld(
                dispatcher, broadphase, solver, collisionConfiguration, softBodySolver
            );

            this.physicsWorld.setGravity(new this.Ammo.btVector3(0, this.gravity, 0));
            this.physicsWorld.getWorldInfo().set_m_gravity(new this.Ammo.btVector3(0, this.gravity, 0));

            this.transformAux = new this.Ammo.btTransform();

            this.initialized = true;
            console.log('[ClothSimulator] Physics world initialized');
            return true;

        } catch (error) {
            console.error('[ClothSimulator] Failed to initialize:', error);
            return false;
        }
    }

    /**
     * Load Ammo.js WASM module
     */
    async _loadAmmo() {
        // Check if already loaded
        if (typeof Ammo !== 'undefined') {
            return Promise.resolve();
        }

        // List of CDN sources to try
        const cdnSources = [
            // Three.js examples CDN (most reliable for Three.js projects)
            'https://unpkg.com/three@0.160.0/examples/jsm/libs/ammo.wasm.js',
            // Direct kripken GitHub
            'https://raw.githubusercontent.com/nickyvanurk/ammo.js/master/builds/ammo.wasm.js',
            // jsDelivr
            'https://cdn.jsdelivr.net/npm/ammo.js@0.0.10/ammo.wasm.js'
        ];

        for (let i = 0; i < cdnSources.length; i++) {
            const src = cdnSources[i];
            console.log(`[ClothSimulator] Trying CDN ${i + 1}/${cdnSources.length}: ${src}`);

            try {
                await this._loadScript(src);
                console.log('[ClothSimulator] Ammo.js loaded successfully');
                return;
            } catch (e) {
                console.warn(`[ClothSimulator] CDN ${i + 1} failed:`, e.message);
            }
        }

        throw new Error('Failed to load Ammo.js from all CDN sources');
    }

    /**
     * Helper to load a script with Promise
     */
    _loadScript(src) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = src;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Failed to load: ${src}`));
            document.head.appendChild(script);
        });
    }

    /**
     * Create a cloth soft body from a Three.js mesh
     * @param {THREE.Mesh} mesh - The clothing mesh
     * @param {Object} options - Cloth simulation options
     * @param {boolean} options.useActualMesh - Apply physics directly to clothing mesh (default: false)
     */
    createClothFromMesh(mesh, options = {}) {
        if (!this.initialized || !mesh.geometry) {
            console.warn('[ClothSimulator] Not initialized or invalid mesh');
            return null;
        }

        // Use actual mesh vertices or create a simplified patch
        if (options.useActualMesh) {
            return this._createFromActualMesh(mesh, options);
        } else {
            return this._createFromPatch(mesh, options);
        }
    }

    /**
     * Create soft body directly from actual mesh vertices using CreateFromTriMesh
     */
    _createFromActualMesh(mesh, options = {}) {
        const geometry = mesh.geometry;
        const positions = geometry.attributes.position;
        const indices = geometry.index;

        if (!positions) {
            console.warn('[ClothSimulator] Mesh has no position attribute');
            return null;
        }

        console.log(`[ClothSimulator] Creating cloth from actual mesh: ${positions.count} vertices`);

        // Get world matrix to transform positions
        mesh.updateMatrixWorld(true);
        const worldMatrix = mesh.matrixWorld;

        const numVertices = positions.count;
        const numTriangles = indices ? indices.count / 3 : numVertices / 3;

        // Allocate Ammo.js memory for vertices
        const vertexFloats = numVertices * 3;
        const vertexPtr = this.Ammo._malloc(vertexFloats * 4); // 4 bytes per float
        const vertexHeap = new Float32Array(this.Ammo.HEAPF32.buffer, vertexPtr, vertexFloats);

        const tempVec = new THREE.Vector3();
        for (let i = 0; i < numVertices; i++) {
            tempVec.set(
                positions.getX(i),
                positions.getY(i),
                positions.getZ(i)
            );
            tempVec.applyMatrix4(worldMatrix);
            vertexHeap[i * 3] = tempVec.x;
            vertexHeap[i * 3 + 1] = tempVec.y;
            vertexHeap[i * 3 + 2] = tempVec.z;
        }

        // Allocate Ammo.js memory for indices
        const indexInts = numTriangles * 3;
        const indexPtr = this.Ammo._malloc(indexInts * 4); // 4 bytes per int
        const indexHeap = new Int32Array(this.Ammo.HEAP32.buffer, indexPtr, indexInts);

        if (indices) {
            for (let i = 0; i < indices.count; i++) {
                indexHeap[i] = indices.getX(i);
            }
        } else {
            for (let i = 0; i < numVertices; i++) {
                indexHeap[i] = i;
            }
        }

        // Create soft body from triangle mesh
        const softBodyHelpers = new this.Ammo.btSoftBodyHelpers();
        const softBody = softBodyHelpers.CreateFromTriMesh(
            this.physicsWorld.getWorldInfo(),
            vertexPtr,
            indexPtr,
            numTriangles,
            true // randomize constraints
        );

        // Free allocated memory
        this.Ammo._free(vertexPtr);
        this.Ammo._free(indexPtr);

        if (!softBody) {
            console.error('[ClothSimulator] Failed to create soft body from mesh');
            return null;
        }

        // Configure soft body
        const clothMass = options.mass || 0.5;
        const sbConfig = softBody.get_m_cfg();
        sbConfig.set_viterations(this.iterations);
        sbConfig.set_piterations(this.iterations);
        sbConfig.set_kDF(0.5); // Dynamic friction
        sbConfig.set_kDP(this.damping); // Damping
        sbConfig.set_kLF(0.0); // Lift
        sbConfig.set_kDG(0.0); // Drag
        sbConfig.set_kPR(0.0); // Pressure

        // Set stiffness
        softBody.get_m_materials().at(0).set_m_kLST(this.stiffness);
        softBody.get_m_materials().at(0).set_m_kAST(this.stiffness);

        // Set mass
        softBody.setTotalMass(clothMass, false);

        // Set margin
        this.Ammo.castObject(softBody, this.Ammo.btCollisionObject)
            .getCollisionShape().setMargin(this.margin);

        // Add to world
        this.physicsWorld.addSoftBody(softBody, 1, -1);

        // Disable deactivation
        softBody.setActivationState(4);

        // Store association - using actual mesh, no separate visualization
        const bbox = new THREE.Box3().setFromBufferAttribute(positions);
        bbox.applyMatrix4(worldMatrix);

        this.softBodies.set(mesh, {
            softBody: softBody,
            originalGeometry: geometry.clone(),
            useActualMesh: true,
            numVertices: numVertices,
            bbox: bbox.clone()
        });

        mesh.userData.isClothSimulated = true;

        console.log(`[ClothSimulator] Cloth created from actual mesh: ${numVertices} vertices, ${numTriangles} triangles`);
        return softBody;
    }

    /**
     * Create soft body using simplified patch (original approach)
     */
    _createFromPatch(mesh, options = {}) {
        const geometry = mesh.geometry;
        const positions = geometry.attributes.position;

        if (!positions) {
            console.warn('[ClothSimulator] Mesh has no position attribute');
            return null;
        }

        console.log(`[ClothSimulator] Creating cloth patch for mesh: ${positions.count} vertices`);

        // Get world matrix to transform positions
        mesh.updateMatrixWorld(true);
        const worldMatrix = mesh.matrixWorld;

        const softBodyHelpers = new this.Ammo.btSoftBodyHelpers();
        const clothMass = options.mass || 0.9;

        // Create a patch based on bounding box
        const bbox = new THREE.Box3().setFromBufferAttribute(positions);
        bbox.applyMatrix4(worldMatrix);

        const size = bbox.getSize(new THREE.Vector3());
        const center = bbox.getCenter(new THREE.Vector3());

        // Create cloth patch
        const clothWidth = size.x;
        const clothHeight = size.y;
        const segmentsX = Math.max(5, Math.min(20, Math.ceil(clothWidth * 10)));
        const segmentsY = Math.max(5, Math.min(20, Math.ceil(clothHeight * 10)));

        const corner00 = new this.Ammo.btVector3(bbox.min.x, bbox.max.y, center.z);
        const corner01 = new this.Ammo.btVector3(bbox.max.x, bbox.max.y, center.z);
        const corner10 = new this.Ammo.btVector3(bbox.min.x, bbox.min.y, center.z);
        const corner11 = new this.Ammo.btVector3(bbox.max.x, bbox.min.y, center.z);

        const softBody = softBodyHelpers.CreatePatch(
            this.physicsWorld.getWorldInfo(),
            corner00, corner01, corner10, corner11,
            segmentsX, segmentsY,
            0, // fixed corners: none by default
            true // generate diagonals
        );

        // Configure soft body
        const sbConfig = softBody.get_m_cfg();
        sbConfig.set_viterations(this.iterations);
        sbConfig.set_piterations(this.iterations);
        sbConfig.set_kDF(0.5); // Dynamic friction
        sbConfig.set_kDP(this.damping); // Damping
        sbConfig.set_kLF(0.0); // Lift
        sbConfig.set_kDG(0.0); // Drag
        sbConfig.set_kPR(0.0); // Pressure

        // Set stiffness
        softBody.get_m_materials().at(0).set_m_kLST(this.stiffness);
        softBody.get_m_materials().at(0).set_m_kAST(this.stiffness);

        // Set mass
        softBody.setTotalMass(clothMass, false);

        // Set margin
        this.Ammo.castObject(softBody, this.Ammo.btCollisionObject)
            .getCollisionShape().setMargin(this.margin * 3);

        // Add to world
        this.physicsWorld.addSoftBody(softBody, 1, -1);

        // Disable deactivation
        softBody.setActivationState(4);

        // Store association
        this.softBodies.set(mesh, {
            softBody: softBody,
            originalGeometry: geometry.clone(),
            segmentsX: segmentsX,
            segmentsY: segmentsY,
            useActualMesh: false,
            bbox: bbox.clone()
        });

        // Create visualization geometry
        this._createClothVisualization(mesh, segmentsX, segmentsY, bbox);

        console.log(`[ClothSimulator] Cloth patch created: ${segmentsX}x${segmentsY} segments`);
        return softBody;
    }

    /**
     * Create visualization geometry for cloth
     * Creates a visible cloth mesh that will be updated by physics
     */
    _createClothVisualization(mesh, segmentsX, segmentsY, bbox) {
        // Get the bounding box from the stored data
        const clothData = this.softBodies.get(mesh);
        if (!clothData) return;

        // Create cloth geometry matching the soft body patch dimensions
        const size = bbox.getSize(new THREE.Vector3());
        const center = bbox.getCenter(new THREE.Vector3());

        const clothGeometry = new THREE.PlaneGeometry(
            size.x,
            size.y,
            segmentsX - 1,
            segmentsY - 1
        );

        // Create cloth material (semi-transparent overlay)
        const clothMaterial = new THREE.MeshLambertMaterial({
            color: 0x8844ff,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.7
        });

        // Create the cloth mesh
        const clothMesh = new THREE.Mesh(clothGeometry, clothMaterial);
        clothMesh.name = 'ClothSimulationOverlay';

        // Position the visual mesh at the bounding box center
        // This aligns it with the soft body's initial position
        clothMesh.position.copy(center);

        // Store references
        clothData.visualMesh = clothMesh;
        clothData.bbox = bbox;
        mesh.userData.clothVisualMesh = clothMesh;
        mesh.userData.isClothSimulated = true;

        // Add to scene - prefer scene reference, fallback to mesh parent
        if (this.scene) {
            this.scene.add(clothMesh);
            console.log('[ClothSimulator] Added visual mesh to scene');
        } else if (mesh.parent) {
            mesh.parent.add(clothMesh);
            console.log('[ClothSimulator] Added visual mesh to mesh parent');
        } else {
            console.warn('[ClothSimulator] No scene or parent to add visual mesh!');
        }

        // Initialize the visual mesh positions from the soft body
        this._initializeVisualFromSoftBody(clothData);

        console.log(`[ClothSimulator] Created visualization mesh: ${segmentsX}x${segmentsY} vertices at center (${center.x.toFixed(2)}, ${center.y.toFixed(2)}, ${center.z.toFixed(2)})`);
    }

    /**
     * Initialize visual mesh vertex positions from soft body nodes
     */
    _initializeVisualFromSoftBody(clothData) {
        const softBody = clothData.softBody;
        const visualMesh = clothData.visualMesh;

        if (!softBody || !visualMesh || !visualMesh.geometry) return;

        const geometry = visualMesh.geometry;
        const positions = geometry.attributes.position;
        const nodes = softBody.get_m_nodes();
        const numNodes = nodes.size();

        console.log(`[ClothSimulator] Initializing ${numNodes} soft body nodes to ${positions.count} visual vertices`);

        // The soft body positions are in world space
        // We need to convert them to the visual mesh's local space
        const worldToLocal = new THREE.Matrix4();
        visualMesh.updateMatrixWorld(true);
        worldToLocal.copy(visualMesh.matrixWorld).invert();

        const tempVec = new THREE.Vector3();

        for (let i = 0; i < numNodes && i < positions.count; i++) {
            const node = nodes.at(i);
            const pos = node.get_m_x();

            // Convert world position to local position
            tempVec.set(pos.x(), pos.y(), pos.z());
            tempVec.applyMatrix4(worldToLocal);

            positions.setXYZ(i, tempVec.x, tempVec.y, tempVec.z);
        }

        geometry.computeVertexNormals();
        positions.needsUpdate = true;
    }

    /**
     * Add an anchor point to attach cloth to a bone/object
     * @param {THREE.Mesh} mesh - The cloth mesh
     * @param {THREE.Object3D} anchor - Object to anchor to
     * @param {number} vertexIndex - Which vertex to anchor
     * @param {number} influence - Anchor influence (0-1)
     */
    addAnchor(mesh, anchor, vertexIndex, influence = 1.0) {
        const clothData = this.softBodies.get(mesh);
        if (!clothData) {
            console.warn('[ClothSimulator] Mesh not found in soft bodies');
            return;
        }

        // Would need a rigid body for the anchor
        // For now, just fix the vertex in place
        clothData.softBody.appendAnchor(vertexIndex, null, false, influence);
    }

    /**
     * Fix vertices at the top of the cloth (for hanging garments)
     * @param {THREE.Mesh} mesh - The cloth mesh
     * @param {number} numToFix - Number of vertices to fix (-1 = auto)
     * @param {number} topPercent - For actual mesh mode, fix vertices in top X% (default 10%)
     */
    fixTopVertices(mesh, numToFix = -1, topPercent = 10) {
        const clothData = this.softBodies.get(mesh);
        if (!clothData) return;

        if (clothData.useActualMesh) {
            // For actual mesh, find vertices near the top of bounding box
            const bbox = clothData.bbox;
            const topThreshold = bbox.max.y - (bbox.max.y - bbox.min.y) * (topPercent / 100);

            const softBody = clothData.softBody;
            const nodes = softBody.get_m_nodes();
            const numNodes = nodes.size();

            let fixedCount = 0;
            for (let i = 0; i < numNodes; i++) {
                const node = nodes.at(i);
                const pos = node.get_m_x();
                if (pos.y() >= topThreshold) {
                    softBody.setMass(i, 0); // Zero mass = fixed
                    fixedCount++;
                }
            }

            console.log(`[ClothSimulator] Fixed ${fixedCount} vertices in top ${topPercent}% of mesh`);
        } else {
            // For patch mode, fix top row
            const segX = clothData.segmentsX;
            if (numToFix < 0) numToFix = segX;

            for (let i = 0; i < Math.min(numToFix, segX); i++) {
                clothData.softBody.setMass(i, 0); // Zero mass = fixed
            }

            console.log(`[ClothSimulator] Fixed top ${numToFix} vertices`);
        }
    }

    /**
     * Add collision with body mesh
     */
    addBodyCollider(bodyMesh) {
        if (!this.initialized || !bodyMesh.geometry) return;

        // Create simplified collision shape from body bounds
        const bbox = new THREE.Box3().setFromObject(bodyMesh);
        const size = bbox.getSize(new THREE.Vector3());
        const center = bbox.getCenter(new THREE.Vector3());

        // Create capsule approximation of body
        const radius = Math.max(size.x, size.z) * 0.3;
        const height = size.y;

        const shape = new this.Ammo.btCapsuleShape(radius, height - radius * 2);
        shape.setMargin(this.margin);

        const transform = new this.Ammo.btTransform();
        transform.setIdentity();
        transform.setOrigin(new this.Ammo.btVector3(center.x, center.y, center.z));

        const motionState = new this.Ammo.btDefaultMotionState(transform);
        const localInertia = new this.Ammo.btVector3(0, 0, 0);

        const rbInfo = new this.Ammo.btRigidBodyConstructionInfo(0, motionState, shape, localInertia);
        const body = new this.Ammo.btRigidBody(rbInfo);

        this.physicsWorld.addRigidBody(body);
        this.rigidBodies.push({ body, mesh: bodyMesh });

        console.log('[ClothSimulator] Added body collider');
    }

    /**
     * Update physics simulation
     * @param {number} deltaTime - Time step in seconds
     */
    update(deltaTime) {
        if (!this.initialized || !this.enabled || this.paused) return;

        // Step physics world
        this.physicsWorld.stepSimulation(deltaTime, 10);

        // Update cloth meshes from soft body positions
        for (const [mesh, clothData] of this.softBodies) {
            this._updateClothMesh(mesh, clothData);
        }
    }

    /**
     * Update cloth mesh vertices from soft body
     */
    _updateClothMesh(mesh, clothData) {
        const softBody = clothData.softBody;

        // Handle actual mesh vs visualization mesh
        if (clothData.useActualMesh) {
            this._updateActualMesh(mesh, clothData);
        } else {
            this._updateVisualizationMesh(mesh, clothData);
        }
    }

    /**
     * Update actual clothing mesh vertices from soft body nodes
     */
    _updateActualMesh(mesh, clothData) {
        const softBody = clothData.softBody;
        const geometry = mesh.geometry;

        if (!geometry || !geometry.attributes.position) return;

        const positions = geometry.attributes.position;
        const nodes = softBody.get_m_nodes();
        const numNodes = nodes.size();

        // Get inverse world matrix to convert world positions to local
        const worldToLocal = new THREE.Matrix4();
        mesh.updateMatrixWorld(true);
        worldToLocal.copy(mesh.matrixWorld).invert();

        const tempVec = new THREE.Vector3();
        let updated = false;

        // Update positions from soft body nodes
        for (let i = 0; i < numNodes && i < positions.count; i++) {
            const node = nodes.at(i);
            const pos = node.get_m_x();

            // Convert world position to local position
            tempVec.set(pos.x(), pos.y(), pos.z());
            tempVec.applyMatrix4(worldToLocal);

            positions.setXYZ(i, tempVec.x, tempVec.y, tempVec.z);
            updated = true;
        }

        if (updated) {
            geometry.computeVertexNormals();
            positions.needsUpdate = true;
            geometry.computeBoundingBox();
            geometry.computeBoundingSphere();
        }
    }

    /**
     * Update visualization mesh vertices from soft body nodes
     */
    _updateVisualizationMesh(mesh, clothData) {
        const softBody = clothData.softBody;
        const visualMesh = clothData.visualMesh;

        // Update the visualization mesh, not the original clothing mesh
        if (!visualMesh || !visualMesh.geometry) return;

        const geometry = visualMesh.geometry;
        const positions = geometry.attributes.position;

        if (!positions) return;

        const nodes = softBody.get_m_nodes();
        const numNodes = nodes.size();
        const expectedNodes = clothData.segmentsX * clothData.segmentsY;

        // Convert world positions to local positions
        const worldToLocal = new THREE.Matrix4();
        visualMesh.updateMatrixWorld(true);
        worldToLocal.copy(visualMesh.matrixWorld).invert();

        const tempVec = new THREE.Vector3();

        // Update positions from soft body nodes
        if (numNodes === expectedNodes || numNodes === positions.count) {
            let updated = false;

            for (let i = 0; i < numNodes && i < positions.count; i++) {
                const node = nodes.at(i);
                const pos = node.get_m_x();

                // Convert world position to local position
                tempVec.set(pos.x(), pos.y(), pos.z());
                tempVec.applyMatrix4(worldToLocal);

                positions.setXYZ(i, tempVec.x, tempVec.y, tempVec.z);
                updated = true;
            }

            if (updated) {
                geometry.computeVertexNormals();
                positions.needsUpdate = true;
            }
        } else {
            // Log mismatch only once
            if (!clothData.nodeMismatchLogged) {
                console.warn(`[ClothSimulator] Node count mismatch: ${numNodes} soft body nodes vs ${positions.count} mesh vertices (expected ${expectedNodes})`);
                clothData.nodeMismatchLogged = true;
            }
        }
    }

    /**
     * Apply wind force to cloth
     */
    applyWind(direction, strength) {
        if (!this.initialized || !this.enabled) return;

        const windForce = new this.Ammo.btVector3(
            direction.x * strength,
            direction.y * strength,
            direction.z * strength
        );

        for (const [mesh, clothData] of this.softBodies) {
            clothData.softBody.addForce(windForce);
        }
    }

    /**
     * Enable/disable simulation
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        console.log(`[ClothSimulator] ${enabled ? 'Enabled' : 'Disabled'}`);
    }

    /**
     * Pause/resume simulation
     */
    setPaused(paused) {
        this.paused = paused;
    }

    /**
     * Remove a cloth mesh from simulation
     */
    removeCloth(mesh) {
        const clothData = this.softBodies.get(mesh);
        if (clothData) {
            this.physicsWorld.removeSoftBody(clothData.softBody);

            // For actual mesh mode, restore original geometry
            if (clothData.useActualMesh && clothData.originalGeometry) {
                mesh.geometry.copy(clothData.originalGeometry);
                mesh.geometry.attributes.position.needsUpdate = true;
                mesh.geometry.computeVertexNormals();
            }

            // Remove visual mesh from scene (for patch mode)
            if (clothData.visualMesh) {
                if (clothData.visualMesh.parent) {
                    clothData.visualMesh.parent.remove(clothData.visualMesh);
                }
                if (clothData.visualMesh.geometry) {
                    clothData.visualMesh.geometry.dispose();
                }
                if (clothData.visualMesh.material) {
                    clothData.visualMesh.material.dispose();
                }
            }

            this.softBodies.delete(mesh);

            // Clean up userData
            delete mesh.userData.clothVisualMesh;
            delete mesh.userData.isClothSimulated;

            console.log('[ClothSimulator] Cloth removed');
        }
    }

    /**
     * Reset all cloth to initial positions
     */
    reset() {
        for (const [mesh, clothData] of this.softBodies) {
            // Remove and recreate soft body
            this.physicsWorld.removeSoftBody(clothData.softBody);
        }
        this.softBodies.clear();
        console.log('[ClothSimulator] Reset');
    }

    /**
     * Clean up all resources
     */
    dispose() {
        this.reset();
        this.rigidBodies = [];
        this.initialized = false;
        console.log('[ClothSimulator] Disposed');
    }
}

export default ClothSimulator;
