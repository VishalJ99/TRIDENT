#!/bin/bash
# Foreground Detection Script
# Run from host: ./cmd.sh
SEGMENTER="grandqc"
OUTPUT_DIR="trident_output_$SEGMENTER"
# Create output directory
mkdir -p $OUTPUT_DIR

# Step 1: Tissue Segmentation (Foreground Detection)
python run_batch_of_slides.py \
    --task seg \
    --wsi_dir wsis \
    --job_dir $OUTPUT_DIR \
    --segmenter $SEGMENTER \
    --gpu 0 \
    --wsi_ext .svs \
    --max_workers 0 \
    --skip_errors

# Step 2: Extract Tissue Coordinates
python run_batch_of_slides.py \
    --task coords \
    --wsi_dir wsis \
    --job_dir $OUTPUT_DIR \
    --mag 20 \
    --patch_size 256 \
    --overlap 0 \
    --wsi_ext .svs \
    --max_workers 0

echo ""
echo "✓ Foreground detection complete!"
echo ""
echo "Results:"
echo "  - Contours (GeoJSON): trident_output/contours_geojson/"
echo "  - Coordinates (HDF5): trident_output/20x_256px/patches/"
echo "  - Visualizations: trident_output/contours/"
