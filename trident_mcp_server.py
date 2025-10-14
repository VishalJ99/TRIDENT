#!/usr/bin/env python3
"""
Trident MCP Server - Natural Language Interface for WSI Foreground Detection

Provides a single tool that combines tissue segmentation and coordinate extraction
from the Trident toolkit into an easy-to-use natural language interface.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent


# Configuration
OUTPUT_DIR = "trident_output"

TRIDENT_ROOT = "./"  # Adjust if needed

# Initialize MCP server
server = Server("trident")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available tools for the Trident MCP server.
    """
    return [
        Tool(
            name="extract_foreground_coords",
            description=(
                "Extract foreground tissue patches from whole-slide images (WSI). "
                "Combines deep learning tissue segmentation with patch coordinate extraction. "
                "Supports .svs, .tif, .ndpi and other standard WSI formats. "
                "Works on single files or entire directories."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    # Required argument
                    "wsi_path": {
                        "type": "string",
                        "description": (
                            "Path to WSI file (.svs, .tif, etc.) or directory containing WSI files. "
                            "Can be absolute or relative to workspace."
                        )
                    },

                    # Generic arguments
                    "gpu": {
                        "type": "integer",
                        "default": 0,
                        "description": "GPU device index to use (0, 1, 2, etc.) or -1 for CPU"
                    },
                    "skip_errors": {
                        "type": "boolean",
                        "default": False,
                        "description": "Skip errored slides and continue processing"
                    },
                    "max_workers": {
                        "type": ["integer", "null"],
                        "default": None,
                        "description": "Maximum number of workers. Set to 0 to use main process. None = auto-detect"
                    },
                    "batch_size": {
                        "type": "integer",
                        "default": 64,
                        "description": "Default batch size for segmentation and feature extraction"
                    },

                    # Caching arguments
                    "wsi_cache": {
                        "type": ["string", "null"],
                        "default": None,
                        "description": "Path to local cache (e.g., SSD) to speed up WSI access from slower drives"
                    },
                    "cache_batch_size": {
                        "type": "integer",
                        "default": 32,
                        "description": "Maximum number of slides to cache locally at once"
                    },

                    # Slide-related arguments
                    "wsi_ext": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "default": None,
                        "description": "List of allowed file extensions (e.g., ['.svs', '.tif']). None = auto-detect"
                    },
                    "custom_mpp_keys": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "default": None,
                        "description": "Custom keys for resolution (MPP - micron per pixel) in WSI metadata"
                    },
                    "custom_list_of_wsis": {
                        "type": ["string", "null"],
                        "default": None,
                        "description": "Path to CSV file with custom list of WSIs to process"
                    },
                    "reader_type": {
                        "type": ["string", "null"],
                        "enum": ["openslide", "image", "cucim", "sdpc", None],
                        "default": None,
                        "description": "Force specific WSI reader. None = auto-detect"
                    },
                    "search_nested": {
                        "type": "boolean",
                        "default": False,
                        "description": "Recursively search for WSIs in subdirectories"
                    },

                    # Segmentation arguments
                    "segmenter": {
                        "type": "string",
                        "enum": ["hest", "grandqc"],
                        "default": "hest",
                        "description": (
                            "Segmentation model. 'hest': Universal, more accurate. "
                            "'grandqc': Faster, optimized for H&E"
                        )
                    },
                    "seg_conf_thresh": {
                        "type": "number",
                        "default": 0.5,
                        "description": (
                            "Segmentation confidence threshold (0.0-1.0). "
                            "Lower = more tissue retained. Try 0.4 if too strict"
                        )
                    },
                    "remove_holes": {
                        "type": "boolean",
                        "default": False,
                        "description": "Remove holes in tissue segmentation masks"
                    },
                    "remove_artifacts": {
                        "type": "boolean",
                        "default": False,
                        "description": "Run additional model to remove artifacts (penmarks, blurs, stains, etc.)"
                    },
                    "remove_penmarks": {
                        "type": "boolean",
                        "default": False,
                        "description": "Run additional model to remove penmarks only"
                    },
                    "seg_batch_size": {
                        "type": ["integer", "null"],
                        "default": None,
                        "description": "Batch size for segmentation. None = use batch_size argument"
                    },

                    # Patching arguments
                    "mag": {
                        "type": "integer",
                        "enum": [5, 10, 20, 40, 80],
                        "default": 20,
                        "description": "Target magnification for patch extraction (5x, 10x, 20x, 40x, 80x)"
                    },
                    "patch_size": {
                        "type": "integer",
                        "default": 512,
                        "description": "Patch size in pixels at target magnification"
                    },
                    "overlap": {
                        "type": "integer",
                        "default": 0,
                        "description": "Absolute overlap between patches in pixels (0 = non-overlapping)"
                    },
                    "min_tissue_proportion": {
                        "type": "number",
                        "default": 0.0,
                        "description": "Minimum proportion of patch under tissue to keep (0.0-1.0)"
                    },
                    "coords_dir": {
                        "type": ["string", "null"],
                        "default": None,
                        "description": "Directory to save/restore tissue coordinates. None = auto-generate path"
                    }
                },
                "required": ["wsi_path"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """
    Execute a tool with the given arguments.
    """
    if name != "extract_foreground_coords":
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]

    return await extract_foreground_coords(arguments)


async def extract_foreground_coords(args: dict[str, Any]) -> list[TextContent]:
    """
    Extract foreground tissue coordinates from WSI files.

    Runs a two-stage pipeline:
    1. Tissue segmentation (deep learning-based foreground detection)
    2. Coordinate extraction (patch coordinate generation within tissue regions)
    """

    # Extract parameters with defaults (matching run_batch_of_slides.py defaults)
    wsi_path = args["wsi_path"]

    # Generic arguments
    gpu = args.get("gpu", 0)
    skip_errors = args.get("skip_errors", False)
    max_workers = args.get("max_workers", None)
    batch_size = args.get("batch_size", 64)

    # Caching arguments
    wsi_cache = args.get("wsi_cache", None)
    cache_batch_size = args.get("cache_batch_size", 32)

    # Slide-related arguments
    wsi_ext = args.get("wsi_ext", None)
    custom_mpp_keys = args.get("custom_mpp_keys", None)
    custom_list_of_wsis = args.get("custom_list_of_wsis", None)
    reader_type = args.get("reader_type", None)
    search_nested = args.get("search_nested", False)

    # Segmentation arguments
    segmenter = args.get("segmenter", "hest")
    seg_conf_thresh = args.get("seg_conf_thresh", 0.5)
    remove_holes = args.get("remove_holes", False)
    remove_artifacts = args.get("remove_artifacts", False)
    remove_penmarks = args.get("remove_penmarks", False)
    seg_batch_size = args.get("seg_batch_size", None)

    # Patching arguments
    mag = args.get("mag", 20)
    patch_size = args.get("patch_size", 512)
    overlap = args.get("overlap", 0)
    min_tissue_proportion = args.get("min_tissue_proportion", 0.0)
    coords_dir = args.get("coords_dir", None)

    # Validate WSI path
    wsi_full_path = Path(TRIDENT_ROOT) / wsi_path
    if not wsi_full_path.exists():
        return [TextContent(
            type="text",
            text=f"❌ Error: Path does not exist: {wsi_path}\n\nPlease check the path and try again."
        )]

    # Create output directory
    output_dir = Path(TRIDENT_ROOT) / OUTPUT_DIR
    output_dir.mkdir(exist_ok=True)

    # Build commands
    python_cmd = sys.executable  # Use same Python as MCP server
    batch_script = Path(TRIDENT_ROOT) / "run_batch_of_slides.py"

    if not batch_script.exists():
        return [TextContent(
            type="text",
            text=f"❌ Error: Trident script not found: {batch_script}\n\nPlease ensure you're in the Trident repository root."
        )]

    # Helper function to build common arguments
    def build_common_args() -> list[str]:
        cmd = []
        cmd.extend(["--job_dir", str(output_dir)])
        cmd.extend(["--wsi_dir", str(wsi_full_path)])
        cmd.extend(["--gpu", str(gpu)])
        cmd.extend(["--batch_size", str(batch_size)])

        if skip_errors:
            cmd.append("--skip_errors")

        if max_workers is not None:
            cmd.extend(["--max_workers", str(max_workers)])

        if wsi_cache is not None:
            cmd.extend(["--wsi_cache", wsi_cache])
            cmd.extend(["--cache_batch_size", str(cache_batch_size)])

        if wsi_ext is not None:
            for ext in wsi_ext:
                cmd.extend(["--wsi_ext", ext])

        if custom_mpp_keys is not None:
            for key in custom_mpp_keys:
                cmd.extend(["--custom_mpp_keys", key])

        if custom_list_of_wsis is not None:
            cmd.extend(["--custom_list_of_wsis", custom_list_of_wsis])

        if reader_type is not None:
            cmd.extend(["--reader_type", reader_type])

        if search_nested:
            cmd.append("--search_nested")

        return cmd

    # Step 1: Tissue Segmentation command
    seg_cmd = [python_cmd, str(batch_script), "--task", "seg"]
    seg_cmd.extend(build_common_args())
    seg_cmd.extend(["--segmenter", segmenter])
    seg_cmd.extend(["--seg_conf_thresh", str(seg_conf_thresh)])

    if remove_holes:
        seg_cmd.append("--remove_holes")
    if remove_artifacts:
        seg_cmd.append("--remove_artifacts")
    if remove_penmarks:
        seg_cmd.append("--remove_penmarks")
    if seg_batch_size is not None:
        seg_cmd.extend(["--seg_batch_size", str(seg_batch_size)])

    # Step 2: Coordinate Extraction command
    coords_cmd = [python_cmd, str(batch_script), "--task", "coords"]
    coords_cmd.extend(build_common_args())
    coords_cmd.extend(["--mag", str(mag)])
    coords_cmd.extend(["--patch_size", str(patch_size)])
    coords_cmd.extend(["--overlap", str(overlap)])
    coords_cmd.extend(["--min_tissue_proportion", str(min_tissue_proportion)])

    if coords_dir is not None:
        coords_cmd.extend(["--coords_dir", coords_dir])

    # Execute pipeline
    output_lines = []
    output_lines.append("🔱 Trident Foreground Detection Pipeline")
    output_lines.append("=" * 50)
    output_lines.append(f"Input: {wsi_path}")
    output_lines.append(f"Segmenter: {segmenter}")
    output_lines.append(f"Magnification: {mag}x")
    output_lines.append(f"Patch size: {patch_size}px")
    output_lines.append(f"GPU: {gpu}")
    output_lines.append("")

    try:
        # Run Step 1: Segmentation
        output_lines.append("📍 Step 1/2: Tissue Segmentation")
        output_lines.append("-" * 50)

        seg_result = subprocess.run(
            seg_cmd,
            capture_output=True,
            text=True,
            cwd=TRIDENT_ROOT
        )

        if seg_result.returncode != 0:
            output_lines.append("❌ Segmentation failed!")
            output_lines.append("")
            output_lines.append("Error output:")
            output_lines.append(seg_result.stderr[-2000:])  # Last 2000 chars
            return [TextContent(type="text", text="\n".join(output_lines))]

        output_lines.append("✓ Segmentation complete")
        output_lines.append("")

        # Run Step 2: Coordinate Extraction
        output_lines.append("📍 Step 2/2: Coordinate Extraction")
        output_lines.append("-" * 50)

        coords_result = subprocess.run(
            coords_cmd,
            capture_output=True,
            text=True,
            cwd=TRIDENT_ROOT
        )

        if coords_result.returncode != 0:
            output_lines.append("❌ Coordinate extraction failed!")
            output_lines.append("")
            output_lines.append("Error output:")
            output_lines.append(coords_result.stderr[-2000:])
            return [TextContent(type="text", text="\n".join(output_lines))]

        output_lines.append("✓ Coordinate extraction complete")
        output_lines.append("")

        # Success! Provide output paths
        output_lines.append("=" * 50)
        output_lines.append("✅ Pipeline Complete!")
        output_lines.append("")
        output_lines.append("📂 Output Locations:")
        output_lines.append(f"  • Contours (GeoJSON): {OUTPUT_DIR}/contours_geojson/")
        output_lines.append(f"  • Coordinates (HDF5): {OUTPUT_DIR}/{mag}x_{patch_size}px/patches/")
        output_lines.append(f"  • Visualizations: {OUTPUT_DIR}/contours/")
        output_lines.append(f"  • Thumbnails: {OUTPUT_DIR}/thumbnails/")
        output_lines.append("")

        # Count output files
        contours_dir = output_dir / "contours_geojson"
        if contours_dir.exists():
            geojson_files = list(contours_dir.glob("*.geojson"))
            output_lines.append(f"📊 Processed {len(geojson_files)} slide(s)")

        coords_dir = output_dir / f"{mag}x_{patch_size}px" / "patches"
        if coords_dir.exists():
            h5_files = list(coords_dir.glob("*.h5"))
            output_lines.append(f"📦 Generated {len(h5_files)} coordinate file(s)")

        return [TextContent(type="text", text="\n".join(output_lines))]

    except Exception as e:
        output_lines.append(f"❌ Unexpected error: {str(e)}")
        return [TextContent(type="text", text="\n".join(output_lines))]


async def main():
    """
    Run the MCP server using stdio transport.
    """
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
