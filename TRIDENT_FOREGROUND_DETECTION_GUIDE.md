# 🔱 Trident WSI Foreground Detection - Complete Guide

## Overview

Trident is a toolkit for large-scale whole-slide image (WSI) processing developed by the Mahmood Lab at Harvard Medical School. This guide focuses on using Trident for foreground patch detection and coordinate extraction.

## High-Level Architecture

The codebase uses a **3-stage pipeline** for WSI processing:

1. **Tissue Segmentation** (Foreground Detection) - Uses deep learning to separate tissue from background
2. **Coordinate Extraction** - Generates patch coordinates within tissue regions
3. **Feature Extraction** - Optionally extracts embeddings from patches

### Core Method: Deep Learning Segmentation

- Uses **DeepLabV3** models (`hest` or `grandqc`) fine-tuned for tissue vs. background segmentation
- Processes WSI at lower magnification (default 10x) for efficiency
- Returns tissue contours as **GeoJSON** format (compatible with QuPath)
- Coordinates saved as **HDF5** files with metadata

---

## 📦 Environment Setup

```bash
# 1. Create conda environment
conda create -n "trident" python=3.10
conda activate trident

# 2. Clone repository
git clone https://github.com/mahmoodlab/trident.git
cd trident

# 3. Install package
pip install -e .

# Note: Additional dependencies may be required for specific models
# Follow error messages for installation instructions
```

---

## 🚀 API Usage

### Option 1: Single WSI (Programmatic API)

```python
from trident.wsi_objects import load_wsi
from trident.segmentation_models.load import segmentation_model_factory

# Load WSI (supports multiple backends)
slide = load_wsi(
    slide_path="path/to/slide.svs",
    lazy_init=False,
    reader_type=None  # Options: 'openslide', 'cucim', 'sdpc', 'image', None (auto)
)

# Initialize segmentation model
segmentation_model = segmentation_model_factory(
    model_name="hest",  # or "grandqc" for faster H&E segmentation
    confidence_thresh=0.5  # Lower = more tissue retained (try 0.4 if too strict)
)

# Step 1: Segment tissue (FOREGROUND DETECTION)
contours_path = slide.segment_tissue(
    segmentation_model=segmentation_model,
    target_mag=10,  # Magnification for segmentation
    job_dir="./output",  # Output directory
    device="cuda:0",  # or "cpu"
    holes_are_tissue=True,  # Set False to exclude holes
    batch_size=16
)
# Outputs:
# - ./output/contours_geojson/<slide_name>.geojson (foreground contours)
# - ./output/contours/<slide_name>.jpg (visualization)
# - ./output/thumbnails/<slide_name>.jpg (thumbnail)

# Step 2: Extract coordinates within foreground regions
coords_path = slide.extract_tissue_coords(
    target_mag=20,  # Magnification for patches
    patch_size=256,  # Patch size in pixels
    save_coords="./output/20x_256px",
    overlap=0,  # Overlap in pixels (0 = non-overlapping)
    min_tissue_proportion=0.0  # Min tissue % to keep patch (0.0 = keep all)
)
# Output: ./output/20x_256px/patches/<slide_name>_patches.h5
# HDF5 contains: coords array (N x 2) with (x, y) coordinates

# Step 3: Visualize coordinates (optional)
viz_path = slide.visualize_coords(
    coords_path=coords_path,
    save_patch_viz="./output/20x_256px/visualization"
)
```

### Option 2: Single WSI (Command-Line)

```bash
python run_single_slide.py \
    --slide_path ./wsis/sample.svs \
    --job_dir ./output \
    --segmenter hest \
    --mag 20 \
    --patch_size 256 \
    --overlap 0 \
    --gpu 0
```

### Option 3: Directory of WSIs (Command-Line)

```bash
# Segmentation only (get foreground contours)
python run_batch_of_slides.py \
    --task seg \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --segmenter hest \
    --seg_conf_thresh 0.5 \
    --gpu 0

# Segmentation + Coordinate extraction
python run_batch_of_slides.py \
    --task coords \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --segmenter hest \
    --mag 20 \
    --patch_size 256 \
    --overlap 0 \
    --gpu 0

# Full pipeline (seg + coords + features)
python run_batch_of_slides.py \
    --task all \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --patch_encoder uni_v1 \
    --mag 20 \
    --patch_size 256 \
    --gpu 0
```

---

## 🔧 WSI Reader Backends

Trident supports **4 different backends** for reading WSI files:

### 1. OpenSlide (Default)

```python
slide = load_wsi(slide_path="path/to/slide.svs")  # Auto-selects OpenSlide
# or explicitly:
slide = load_wsi(slide_path="path/to/slide.svs", reader_type='openslide')
```

**Supported formats:** `.svs`, `.tif`, `.tiff`, `.ndpi`, `.vms`, `.vmu`, `.scn`, `.mrxs`, `.bif`

### 2. CuCIM (NVIDIA GPU-Accelerated)

```python
slide = load_wsi(slide_path="path/to/slide.svs", reader_type='cucim')
```

```bash
# Command-line usage
python run_batch_of_slides.py \
    --task seg \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --reader_type cucim \
    --gpu 0
```

**Benefits:** GPU-accelerated reading for faster processing
**Note:** Requires separate CuCIM installation

### 3. SDPC (Specialized Format)

```python
slide = load_wsi(slide_path="path/to/slide.sdpc", reader_type='sdpc')
```

### 4. PIL Image (Fallback)

```python
slide = load_wsi(slide_path="path/to/image.png", reader_type='image')
```

For standard image formats (`.png`, `.jpg`, etc.)

### Backend Selection Logic

```python
# Auto-detection when reader_type=None (default):
# 1. If extension in OPENSLIDE_EXTENSIONS → OpenSlideWSI
# 2. If extension in SDPC_EXTENSIONS → SDPCWSI
# 3. Else → ImageWSI (PIL)
```

---

## 📂 Output Structure

```
output/
├── thumbnails/              # WSI thumbnails
│   └── slide_name.jpg
├── contours/               # Thumbnails with tissue contours drawn
│   └── slide_name.jpg
├── contours_geojson/       # FOREGROUND REGIONS (GeoJSON format)
│   └── slide_name.geojson  # Compatible with QuPath
└── 20x_256px/             # Patch coordinates (named by mag + patch size)
    ├── patches/
    │   └── slide_name_patches.h5  # COORDINATES (x, y) in HDF5
    └── visualization/
        └── slide_name.jpg         # Patches drawn on thumbnail
```

---

## 🔍 Reading Coordinates from HDF5

```python
import h5py
import numpy as np

# Load coordinates
with h5py.File("output/20x_256px/patches/slide_name_patches.h5", 'r') as f:
    coords = np.array(f['coords'])  # Shape: (N, 2) - (x, y) pairs

    # Metadata
    patch_size = f.attrs['patch_size']
    patch_size_level0 = f.attrs['patch_size_level0']
    magnification = f.attrs['target_magnification']
    base_mag = f.attrs['level0_magnification']
    overlap = f.attrs['overlap']

print(f"Found {len(coords)} foreground patches")
print(f"Patch size: {patch_size}px at {magnification}x magnification")
print(f"First 5 coordinates (x, y):\n{coords[:5]}")

# Coordinates are in level 0 (base resolution) reference frame
# Each (x, y) is the top-left corner of the patch
```

---

## ⚙️ Key Parameters

### Segmentation Parameters

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `--segmenter` | Segmentation model | `hest` | Options: `hest`, `grandqc` |
| `--seg_conf_thresh` | Confidence threshold | `0.5` | Lower = more tissue retained (try 0.4) |
| `--remove_holes` | Exclude holes in tissue | `False` | Set True to fill holes |
| `--remove_artifacts` | Remove artifacts/penmarks | `False` | Additional cleanup pass |
| `--remove_penmarks` | Remove only penmarks | `False` | Lighter than remove_artifacts |
| `--seg_batch_size` | Batch size for segmentation | `None` | Uses `--batch_size` if None |

### Patching Parameters

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `--mag` | Patch magnification | `20` | Options: 5, 10, 20, 40, 80 |
| `--patch_size` | Patch size in pixels | `256` | At target magnification |
| `--overlap` | Absolute overlap in pixels | `0` | Not percentage - actual pixels |
| `--min_tissue_proportion` | Min tissue % per patch | `0.0` | Range: 0.0-1.0 |
| `--coords_dir` | Custom coords directory | `None` | Override default location |

### Reader Parameters

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `--reader_type` | WSI reader backend | `None` | Options: `openslide`, `cucim`, `sdpc`, `image` |
| `--custom_mpp_keys` | Custom MPP metadata keys | `None` | For non-standard WSI formats |
| `--search_nested` | Search subdirectories | `False` | Recursive WSI search |

### Processing Parameters

| Parameter | Description | Default | Notes |
|-----------|-------------|---------|-------|
| `--gpu` | GPU index | `0` | Use `-1` for CPU |
| `--batch_size` | Default batch size | `64` | For seg and feature extraction |
| `--skip_errors` | Skip failed slides | `False` | Continue on errors |
| `--max_workers` | Max parallel workers | `None` | Set to 0 for main process only |

---

## 🎯 Key Files in Codebase

| File | Line | Description |
|------|------|-------------|
| `trident/wsi_objects/WSI.py` | 364 | `segment_tissue()` - Foreground detection |
| `trident/wsi_objects/WSI.py` | 633 | `extract_tissue_coords()` - Coordinate extraction |
| `trident/wsi_objects/WSIPatcher.py` | 12 | `WSIPatcher` class - Patch generation logic |
| `trident/wsi_objects/WSIFactory.py` | 16 | `load_wsi()` - Multi-backend loader |
| `trident/Processor.py` | 165 | `run_segmentation_job()` - Batch segmentation |
| `trident/Processor.py` | 275 | `run_patching_job()` - Batch patching |
| `trident/IO.py` | 529 | `coords_to_h5()` - Save coordinates to HDF5 |
| `run_single_slide.py` | 51 | `process_slide()` - Single WSI pipeline |
| `run_batch_of_slides.py` | - | Batch processing script |

---

## 💡 Tips and Best Practices

### Quality Control

1. **Always review segmentation outputs** in `./output/contours/` directory
2. **Check patch visualizations** in `./output/<mag>x_<size>px/visualization/`
3. **Edit contours in QuPath** if needed - GeoJSON format is compatible

### Performance Optimization

1. **Use CuCIM backend** for GPU-accelerated reading:
   ```bash
   --reader_type cucim
   ```

2. **Cache WSIs on local SSD** for faster access:
   ```bash
   --wsi_cache /path/to/local/ssd
   ```

3. **Multiprocessing** - Run multiple instances in parallel (they auto-coordinate via lockfiles)

4. **Adjust batch size** based on GPU memory:
   ```bash
   --batch_size 128  # Increase for more VRAM
   ```

### Common Issues

1. **Too much background included**: Lower `--seg_conf_thresh` to 0.4
2. **Missing tissue regions**: Increase `--seg_conf_thresh` or switch segmenter
3. **Artifacts causing issues**: Use `--remove_artifacts` flag
4. **Slow processing**: Use `--reader_type cucim` or enable caching

---

## 📚 Additional Resources

- **Documentation**: https://trident-docs.readthedocs.io/en/latest/
- **Paper**: https://arxiv.org/pdf/2502.06750
- **GitHub**: https://github.com/mahmoodlab/trident
- **Tutorials**: See `tutorials/` directory for Jupyter notebooks

---

## 🔬 Use Case: Extract Foreground Coordinates Only

If you only want foreground coordinates (no feature extraction):

```bash
# Step 1: Segmentation
python run_batch_of_slides.py \
    --task seg \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --segmenter hest \
    --gpu 0

# Step 2: Coordinate extraction
python run_batch_of_slides.py \
    --task coords \
    --wsi_dir ./wsis \
    --job_dir ./output \
    --mag 20 \
    --patch_size 256 \
    --overlap 0

# Results:
# - ./output/contours_geojson/<slide>.geojson  (foreground contours)
# - ./output/20x_256px/patches/<slide>_patches.h5  (coordinates)
```

---

## License

This codebase is released under **CC-BY-NC-ND 4.0** license by Mahmood Lab.
For non-commercial, academic research purposes only.
