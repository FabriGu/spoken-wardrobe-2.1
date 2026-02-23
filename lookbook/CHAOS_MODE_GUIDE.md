# Dreamwear Lookbook - CHAOS MODE

## Changes Made

### Bugs Fixed
1. ✅ `outputEncoding` → `outputColorSpace` (Three.js deprecation)
2. ✅ Missing `glow` and `diagonal` shaders added to library
3. ✅ Const assignment bug fixed in ShaderPlaneElement
4. ✅ On-demand image loading from URLs now supported

### Maximum Chaos Features

#### 1. Dense Compositions
- **Before**: 8-12 elements per composition
- **After**: 25-40 elements per composition
- Heavy overlap encouraged
- Random depth ordering

#### 2. Visual Noise
- Elements scattered everywhere (not just avoiding center)
- Multiple instances of same images
- Chaotic rotation angles: 0°, 30°, 45°, 60°, 90°, 120°, 150°, 180°, etc.
- Black backgrounds for maximum contrast

#### 3. On-Demand Imagery
Images fetched dynamically from Unsplash based on keywords:
```javascript
"path": "https://source.unsplash.com/random/400x400?red"
```

Loaded when composition is viewed - no local storage needed.

#### 4. Animated Everything
- All meshes float, breathe, rotate
- All shader planes animate
- Text drifts slowly
- Chaotic timing (different speeds for each element)

---

## Test It

### 1. Start Server
```bash
cd lookbook
python3 server.py
```

### 2. View Test (Maximum Chaos)
http://localhost:8081/composition.html?id=test

You should see:
- 50+ overlapping elements
- Black background
- Text at all angles
- Diagonal strips cutting through
- Everything animating chaotically

### 3. View Real Composition
http://localhost:8081/composition.html?id=1765268852

- 30-40 elements
- Multiple overlapping images
- Web images loading from Unsplash
- Animated mesh

---

## Regenerate All Compositions

```bash
cd lookbook/preprocessing
python3 composition_generator_chaos.py
```

This creates 73 compositions with:
- 25-40 elements each
- On-demand Unsplash images
- Maximum overlap
- Chaotic positioning

---

## Print is Frozen

When you press `P` or click "Export Print":
- Captures current animation frame
- 4096x4096 PNG
- That moment is frozen forever
- Chaos crystallized into a single image

---

## Element Count Examples

| Session | Elements | Description |
|---------|----------|-------------|
| 1765268852 | 37 | "red nice t-shirt" - many red shaders, overlapping |
| 1765596014 | 34 | "red clown" - glitch shaders, chaotic mesh |
| 1764637901 | 36 | "red t-shirt" - dense image overlap |

---

## Technical Notes

### URL Loading
Images from Unsplash load with `crossOrigin: "anonymous"` - this allows them to be captured in screenshots.

### Performance
- 25-40 elements is heavy but manageable
- Shaders run on GPU
- Animation uses requestAnimationFrame
- If slow: reduce shader count or disable animations

### Randomness
Each reload gives slightly different:
- Element positions
- Shader selection
- Rotation angles
- Animation timing

The composition JSON is static, but the chaos is alive.

---

**Embrace the noise. Print the dream.**
