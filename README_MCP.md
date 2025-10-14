# 🔱 Trident MCP Server - Installation & Usage Guide

Natural language interface for Trident WSI foreground detection, powered by Model Context Protocol (MCP).

## What This Does

Allows you to use Claude Code with natural language commands instead of remembering complex CLI arguments:

**Instead of this:**
```bash
python run_batch_of_slides.py --task seg --wsi_dir wsis --job_dir output --segmenter hest --seg_conf_thresh 0.5 --gpu 0 --wsi_ext .svs --max_workers 0 --skip_errors
python run_batch_of_slides.py --task coords --wsi_dir wsis --job_dir output --mag 20 --patch_size 256 --overlap 0 --wsi_ext .svs --max_workers 0
```

**You can say this:**
```
"Extract foreground patches from wsis/ using hest"
```

---

## Prerequisites

1. **Python environment with MCP SDK installed**
   ```bash
   pip install mcp
   ```

2. **Trident repository** (this codebase)
   - Must be located at `/workspace/` or update `TRIDENT_ROOT` in server script

3. **Claude Code** installed and configured

4. Set TRIDENT_PYTHON env var to trident python bin path.
---

## Installation

### Step 1: Verify MCP Server Script

Ensure `trident_mcp_server.py` exists in your Trident repository root:
```bash
ls /workspace/trident_mcp_server.py
```

Make it executable (optional but recommended):
```bash
chmod +x /workspace/trident_mcp_server.py
```

### Step 2: Configure Claude Code

Add the Trident MCP server to Claude Code's configuration file.

**Location:** `~/.claude/claude_desktop_config.json`

**Add this entry:**
```json
{
  "mcpServers": {
    "trident": {
      "command": "python3",
      "args": ["/workspace/trident_mcp_server.py"]
    }
  }
}
```

**Full example config:**
```json
{
  "mcpServers": {
    "trident": {
      "command": "python3",
      "args": ["/workspace/trident_mcp_server.py"]
    },
    "other-server": {
      "command": "...",
      "args": ["..."]
    }
  }
}
```

**Important:** Replace `/workspace/trident_mcp_server.py` with the absolute path to your server script.

### Step 3: Restart Claude Code

Close and reopen Claude Code to load the new MCP server.

### Step 4: Verify Installation

In Claude Code, you should see the Trident MCP server listed in the MCP servers panel.

Ask Claude: "What MCP tools are available?"

You should see `extract_foreground_coords` listed.

---

## Usage

### Basic Examples

**Process a single slide:**
```
"Extract patches from wsis/case_042.svs"
```

**Process entire directory:**
```
"Extract foreground coordinates from all slides in wsis/"
```

**Specify segmentation model:**
```
"Use grandqc to segment wsis/case_001.svs"
```

**Change magnification:**
```
"Extract patches at 40x magnification from wsis/"
```

**Combine parameters:**
```
"Process wsis/ using hest at 20x with 512px patches"
```

**Use different GPU:**
```
"Extract patches on GPU 1 from wsis/slide.svs"
```

**Adjust confidence threshold:**
```
"Segment with confidence 0.4 to retain more tissue"
```

### Advanced Examples

**High-resolution patches:**
```
"Extract 40x magnification with 512px patches and 64px overlap"
```

**CPU processing:**
```
"Use CPU to process wsis/case_042.svs"
```
(Claude will set `gpu=-1`)

**Quality control:**
```
"Process with lower confidence threshold because tissue is faint"
```
(Claude will set `confidence_thresh=0.4`)

---

## Tool Parameters

### `extract_foreground_coords`

**All parameters from `run_batch_of_slides.py` are now exposed with their original defaults.**

**Required:**
- `wsi_path` - Path to WSI file or directory
  - Examples: `"wsis/case_001.svs"`, `"wsis/"`, `"./slides/tcga/"`

**Generic Arguments:**
- `gpu` - GPU device index (default: `0`, use `-1` for CPU)
- `skip_errors` - Skip errored slides and continue (default: `False`)
- `max_workers` - Maximum number of workers (default: `None` = auto-detect, `0` = main process)
- `batch_size` - Default batch size for processing (default: `64`)

**Caching Arguments:**
- `wsi_cache` - Path to local cache directory for faster WSI access (default: `None`)
- `cache_batch_size` - Maximum slides to cache at once (default: `32`)

**Slide-Related Arguments:**
- `wsi_ext` - List of allowed file extensions (default: `None` = auto-detect)
  - Example: `[".svs", ".tif", ".ndpi"]`
- `custom_mpp_keys` - Custom MPP (micron per pixel) metadata keys (default: `None`)
- `custom_list_of_wsis` - Path to CSV file with custom WSI list (default: `None`)
- `reader_type` - Force specific WSI reader (default: `None` = auto-detect)
  - Options: `"openslide"`, `"image"`, `"cucim"`, `"sdpc"`
- `search_nested` - Recursively search subdirectories (default: `False`)

**Segmentation Arguments:**
- `segmenter` - Segmentation model (default: `"hest"`)
  - `"hest"` - More accurate, universal tissue detection
  - `"grandqc"` - Faster, optimized for H&E slides
- `seg_conf_thresh` - Segmentation confidence threshold 0.0-1.0 (default: `0.5`)
  - Lower values retain more tissue. Try `0.4` if too strict
- `remove_holes` - Remove holes in tissue masks (default: `False`)
- `remove_artifacts` - Run additional artifact removal model (default: `False`)
  - Removes penmarks, blurs, stains, etc.
- `remove_penmarks` - Run penmark removal only (default: `False`)
- `seg_batch_size` - Batch size for segmentation (default: `None` = use `batch_size`)

**Patching Arguments:**
- `mag` - Target magnification (default: `20`)
  - Options: `5`, `10`, `20`, `40`, `80`
- `patch_size` - Patch size in pixels (default: `512`)
  - Common values: `224`, `256`, `512`, `1024`
- `overlap` - Overlap between patches in pixels (default: `0`)
  - Example: `64` for 25% overlap with 256px patches
- `min_tissue_proportion` - Minimum tissue proportion to keep patch 0.0-1.0 (default: `0.0`)
- `coords_dir` - Directory to save/restore coordinates (default: `None` = auto-generate)

---

## Output Structure

Results are saved to `trident_output/` directory:

```
trident_output/
├── thumbnails/                # WSI thumbnails
│   └── slide_name.jpg
├── contours/                 # Visualizations with tissue contours
│   └── slide_name.jpg
├── contours_geojson/         # GeoJSON tissue masks (QuPath compatible)
│   └── slide_name.geojson
└── 20x_256px/               # Named by magnification + patch size
    ├── patches/
    │   └── slide_name_patches.h5  # HDF5 with (x, y) coordinates
    └── visualization/
        └── slide_name.jpg         # Patches visualized on thumbnail
```

### Reading Coordinates

```python
import h5py
import numpy as np

with h5py.File("trident_output/20x_256px/patches/slide_patches.h5", 'r') as f:
    coords = np.array(f['coords'])  # Shape: (N, 2)

    # Metadata
    patch_size = f.attrs['patch_size']
    magnification = f.attrs['target_magnification']

print(f"Found {len(coords)} foreground patches")
print(f"First 5 coordinates:\n{coords[:5]}")
```

---

## Troubleshooting

### Server Not Appearing in Claude Code

**Check config file syntax:**
```bash
cat ~/.claude/claude_desktop_config.json | python3 -m json.tool
```

**Verify Python path:**
```bash
which python3
```
Use the actual path in the config.

**Check server script:**
```bash
python3 /workspace/trident_mcp_server.py
```
Should not error immediately (will wait for stdin).

### "Path does not exist" Error

**Check working directory:**
- Paths are relative to `/workspace/` by default
- Use absolute paths if unsure: `"/full/path/to/wsis/"`

**Verify WSI files exist:**
```bash
ls /workspace/wsis/
```

### "Trident script not found" Error

**Verify `run_batch_of_slides.py` exists:**
```bash
ls /workspace/run_batch_of_slides.py
```

**Update `TRIDENT_ROOT` in server script:**
Edit line 19 of `trident_mcp_server.py`:
```python
TRIDENT_ROOT = "/actual/path/to/trident"
```

### Segmentation or Coordinate Extraction Fails

**Check dependencies:**
```bash
python3 -c "import torch; print(torch.__version__)"
python3 -c "from trident.wsi_objects import load_wsi"
```

**Check GPU availability:**
```bash
nvidia-smi
```

**Try CPU mode:**
```
"Process using CPU"
```

**View detailed errors:**
The MCP server captures stderr. Ask Claude to show the full error output.

---

## Configuration

### Changing Default Output Directory

Edit `trident_mcp_server.py` line 18:
```python
OUTPUT_DIR = "my_custom_output"
```

### Changing Trident Root Path

Edit `trident_mcp_server.py` line 19:
```python
TRIDENT_ROOT = "/path/to/your/trident"
```

### Using Conda Environment

If Trident is in a conda environment, update the config to activate it:

```json
{
  "mcpServers": {
    "trident": {
      "command": "bash",
      "args": [
        "-c",
        "source /path/to/conda/etc/profile.d/conda.sh && conda activate trident && python /workspace/trident_mcp_server.py"
      ]
    }
  }
}
```

---

## Testing

### Manual Test (Without Claude Code)

Test the server directly using the MCP inspector:

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run inspector
mcp-inspector python3 /workspace/trident_mcp_server.py
```

Open the web interface and test the `extract_foreground_coords` tool.

### End-to-End Test

1. Ensure you have a test WSI file:
   ```bash
   ls /workspace/wsis/test_slide.svs
   ```

2. In Claude Code, ask:
   ```
   "Extract patches from wsis/test_slide.svs using hest"
   ```

3. Check outputs:
   ```bash
   ls trident_output/contours_geojson/
   ls trident_output/20x_256px/patches/
   ```

---

## Expanding the Server

To add more tools (e.g., feature extraction, visualization):

1. Add new tool definitions to `list_tools()`
2. Add new handlers in `call_tool()`
3. Restart Claude Code to load changes

Example structure:
```python
@server.list_tools()
async def list_tools():
    return [
        Tool(name="extract_foreground_coords", ...),
        Tool(name="extract_patch_features", ...),  # New tool
        Tool(name="visualize_segmentation", ...)   # New tool
    ]
```

---

## Support

**Trident Documentation:** https://trident-docs.readthedocs.io/en/latest/

**Trident GitHub:** https://github.com/mahmoodlab/trident

**MCP Documentation:** https://modelcontextprotocol.io/

---

## License

This MCP server wrapper is provided as-is. The underlying Trident toolkit is released under CC-BY-NC-ND 4.0 by Mahmood Lab.
