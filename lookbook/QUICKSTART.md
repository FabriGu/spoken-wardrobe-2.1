# Lookbook Quickstart

## Run Server
```bash
cd lookbook
python3 server.py --port 8081
```
Open: http://localhost:8081/composition.html?id=test

## Regenerate Compositions

### 1. Generate without external images (fast)
```bash
cd lookbook/preprocessing
python3 composition_generator.py
```

### 2. Generate with downloaded images (recommended)
```bash
cd lookbook/preprocessing
python3 composition_generator.py --fetch-images -n 5
```

### 3. With Pexels API (higher quality images)
```bash
export PEXELS_API_KEY="your_key"
python3 composition_generator.py --fetch-images -n 10
```

## View Compositions

| URL | Description |
|-----|-------------|
| `http://localhost:8081/composition.html?id=test` | Test composition |
| `http://localhost:8081/composition.html?id=<timestamp>` | Specific session |
| `http://localhost:8081/index.html` | Gallery view |

Use arrow keys or click edges to navigate between compositions.

## Debug Checklist

| Issue | Check |
|-------|-------|
| Shader errors | Console should be clean after fixes |
| CORS errors | Run `--fetch-images` to download locally |
| Mesh hidden | Compositions need regeneration |
| No compositions | Check `lookbook/compositions/*.json` exists |

## File Locations

```
lookbook/
├── server.py              # HTTP server
├── compositions/          # Generated JSON configs
├── found_images/          # Downloaded external images
├── static/js/
│   ├── AnamorphicScene.js # Main scene
│   ├── shaders/           # Shader library
│   └── elements/          # Mesh, image, text loaders
└── preprocessing/
    ├── composition_generator.py  # Generates configs
    ├── found_imagery_fetcher.py  # Downloads images
    └── keyword_extractor.py      # Extracts keywords
```
