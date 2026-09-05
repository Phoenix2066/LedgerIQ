/**
 * LedgerIQ — 3D WebGL Three.js Interactive Particle Network
 * Creates an elegant, ambient constellation of floating financial data nodes
 * connected by dynamic energy lines that respond softly to mouse movement.
 */

class FinanceNetworkVisualizer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container || typeof THREE === 'undefined') return;

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.particles = null;
    this.linesMesh = null;
    this.particlePositions = [];
    this.particleVelocities = [];
    
    this.particleCount = 110;
    this.maxDistance = 140;
    
    this.mouseX = 0;
    this.mouseY = 0;
    this.targetMouseX = 0;
    this.targetMouseY = 0;
    this.windowHalfX = window.innerWidth / 2;
    this.windowHalfY = window.innerHeight / 2;
    
    this.animationFrameId = null;

    this.init();
  }

  init() {
    // 1. Scene
    this.scene = new THREE.Scene();

    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      1,
      2000
    );
    this.camera.position.z = 500;

    // 3. Renderer
    this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    // 4. Create Particles & Velocity vectors
    const isLight = document.documentElement.getAttribute('data-theme') === 'light';
    const particleColor = isLight ? 0x4f46e5 : 0x818cf8;
    const lineColor = isLight ? 0x6366f1 : 0x06b6d4;

    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(this.particleCount * 3);
    const colors = new Float32Array(this.particleCount * 3);

    const color1 = new THREE.Color(particleColor);
    const color2 = new THREE.Color(lineColor);

    const r = 450;
    for (let i = 0; i < this.particleCount; i++) {
      const x = Math.random() * r * 2 - r;
      const y = Math.random() * r * 2 - r;
      const z = Math.random() * r * 2 - r;

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;

      this.particlePositions.push({ x, y, z });
      this.particleVelocities.push({
        vx: (Math.random() - 0.5) * 0.6,
        vy: (Math.random() - 0.5) * 0.6,
        vz: (Math.random() - 0.5) * 0.6,
      });

      const mix = Math.random();
      const mixed = color1.clone().lerp(color2, mix);
      colors[i * 3] = mixed.r;
      colors[i * 3 + 1] = mixed.g;
      colors[i * 3 + 2] = mixed.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    // Particle Material
    const pMaterial = new THREE.PointsMaterial({
      size: 4.5,
      vertexColors: true,
      transparent: true,
      opacity: isLight ? 0.75 : 0.85,
      blending: THREE.AdditiveBlending,
    });

    this.particles = new THREE.Points(geometry, pMaterial);
    this.scene.add(this.particles);

    // 5. Lines linking nearby particles
    const linePositions = new Float32Array(this.particleCount * this.particleCount * 3);
    const lineColors = new Float32Array(this.particleCount * this.particleCount * 3);
    const lineGeometry = new THREE.BufferGeometry();
    
    lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
    lineGeometry.setAttribute('color', new THREE.BufferAttribute(lineColors, 3));

    const lineMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: isLight ? 0.25 : 0.35,
      blending: THREE.AdditiveBlending,
    });

    this.linesMesh = new THREE.LineSegments(lineGeometry, lineMaterial);
    this.scene.add(this.linesMesh);

    // Event listeners
    window.addEventListener('resize', this.onWindowResize.bind(this));
    window.addEventListener('mousemove', this.onMouseMove.bind(this));

    // Start loop
    this.animate();
  }

  onWindowResize() {
    this.windowHalfX = window.innerWidth / 2;
    this.windowHalfY = window.innerHeight / 2;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
  }

  onMouseMove(e) {
    this.targetMouseX = (e.clientX - this.windowHalfX) * 0.25;
    this.targetMouseY = (e.clientY - this.windowHalfY) * 0.25;
  }

  updateThemeColors(isLight) {
    if (!this.particles || !this.linesMesh) return;
    const particleColor = isLight ? 0x4f46e5 : 0x818cf8;
    const lineColor = isLight ? 0x6366f1 : 0x06b6d4;
    this.particles.material.opacity = isLight ? 0.75 : 0.85;
    this.linesMesh.material.opacity = isLight ? 0.22 : 0.35;
  }

  animate() {
    this.animationFrameId = requestAnimationFrame(this.animate.bind(this));

    // Soft camera lag
    this.mouseX += (this.targetMouseX - this.mouseX) * 0.05;
    this.mouseY += (this.targetMouseY - this.mouseY) * 0.05;

    this.camera.position.x = this.mouseX;
    this.camera.position.y = -this.mouseY;
    this.camera.lookAt(this.scene.position);

    const positions = this.particles.geometry.attributes.position.array;
    const linePositions = this.linesMesh.geometry.attributes.position.array;
    const lineColors = this.linesMesh.geometry.attributes.color.array;

    const r = 450;
    let vertexpos = 0;
    let colorpos = 0;

    for (let i = 0; i < this.particleCount; i++) {
      const p = this.particlePositions[i];
      const v = this.particleVelocities[i];

      p.x += v.vx;
      p.y += v.vy;
      p.z += v.vz;

      // Bounce off sphere bounds
      if (p.x < -r || p.x > r) v.vx = -v.vx;
      if (p.y < -r || p.y > r) v.vy = -v.vy;
      if (p.z < -r || p.z > r) v.vz = -v.vz;

      positions[i * 3] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;

      // Check connections
      for (let j = i + 1; j < this.particleCount; j++) {
        const pj = this.particlePositions[j];
        const dx = p.x - pj.x;
        const dy = p.y - pj.y;
        const dz = p.z - pj.z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

        if (dist < this.maxDistance) {
          const alpha = 1.0 - dist / this.maxDistance;

          linePositions[vertexpos++] = p.x;
          linePositions[vertexpos++] = p.y;
          linePositions[vertexpos++] = p.z;

          linePositions[vertexpos++] = pj.x;
          linePositions[vertexpos++] = pj.y;
          linePositions[vertexpos++] = pj.z;

          lineColors[colorpos++] = 0.39 * alpha;
          lineColors[colorpos++] = 0.40 * alpha;
          lineColors[colorpos++] = 0.95 * alpha;

          lineColors[colorpos++] = 0.02 * alpha;
          lineColors[colorpos++] = 0.71 * alpha;
          lineColors[colorpos++] = 0.83 * alpha;
        }
      }
    }

    this.particles.geometry.attributes.position.needsUpdate = true;
    this.linesMesh.geometry.attributes.position.needsUpdate = true;
    this.linesMesh.geometry.attributes.color.needsUpdate = true;
    this.linesMesh.geometry.setDrawRange(0, vertexpos / 3);

    // Subtle scene rotation
    this.scene.rotation.y += 0.0012;
    this.scene.rotation.x += 0.0006;

    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
    if (this.renderer && this.renderer.domElement) {
      this.renderer.domElement.remove();
    }
  }
}

window.FinanceNetworkVisualizer = FinanceNetworkVisualizer;
