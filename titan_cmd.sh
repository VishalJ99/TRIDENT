#!/bin/bash
# Titan Slide Embedding Extraction Script
# Run from host: ./titan_cmd.sh
SEGMENTER="hest"
OUTPUT_DIR="trident_output_$SEGMENTER"
PYTHON_BIN="/vol/biomedic3/vj724/.conda/envs/trident/bin/python"

# Create output directory
mkdir -p $OUTPUT_DIR

echo "========================================="
echo "Titan Slide Embedding Pipeline"
echo "========================================="
echo ""

# Step 1: Tissue Segmentation (Foreground Detection)
echo "[Step 1/3] Running tissue segmentation..."
$PYTHON_BIN run_batch_of_slides.py \
    --task seg \
    --wsi_dir wsis \
    --job_dir $OUTPUT_DIR \
    --segmenter $SEGMENTER \
    --gpu 0 \
    --wsi_ext .svs \
    --max_workers 0 \
    --skip_errors

echo ""
echo "✓ Segmentation complete!"
echo ""

# Step 2: Extract Tissue Coordinates (512px for Titan/CONCHv1.5)
echo "[Step 2/3] Extracting tissue coordinates (512px patches @ 20x)..."
$PYTHON_BIN run_batch_of_slides.py \
    --task coords \
    --wsi_dir wsis \
    --job_dir $OUTPUT_DIR \
    --mag 20 \
    --patch_size 512 \
    --overlap 0 \
    --wsi_ext .svs \
    --max_workers 0

echo ""
echo "✓ Coordinate extraction complete!"
echo ""

# Step 3: Extract Titan Slide Embeddings
# This will automatically:
# 1. Extract CONCHv1.5 patch features (if not already done)
# 2. Extract Titan slide-level embeddings from patch features
echo "[Step 3/3] Extracting Titan slide embeddings..."
echo "(This will auto-extract CONCHv1.5 patch features first if needed)"
$PYTHON_BIN run_batch_of_slides.py \
    --task feat \
    --wsi_dir wsis \
    --job_dir $OUTPUT_DIR \
    --slide_encoder titan \
    --mag 20 \
    --patch_size 512 \
    --gpu 0 \
    --wsi_ext .svs \
    --max_workers 0 \
    --skip_errors

echo ""
echo "========================================="
echo "✓ Titan Pipeline Complete!"
echo "========================================="
echo ""
echo "Results:"
echo "  - Contours (GeoJSON): $OUTPUT_DIR/contours_geojson/"
echo "  - Coordinates (HDF5): $OUTPUT_DIR/20x_512px/patches/"
echo "  - Patch Features (CONCHv1.5): $OUTPUT_DIR/20x_512px/features_conch_v15/"
echo "  - Slide Embeddings (Titan): $OUTPUT_DIR/20x_512px/slide_features_titan/"
echo ""
