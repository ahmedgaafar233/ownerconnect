#!/bin/bash

# Configuration
BASE_URL="http://127.0.0.1:8000/admin/"
PROFILES_DIR="/tmp/ownerconnect_profiles"

# Create profiles directory if it doesn't exist
mkdir -p "$PROFILES_DIR"

# Roles to open (excluding SuperAdmin since user already has it)
ROLES=("General_Manager" "Financial_Manager" "Supervisor" "Data_Entry")

# Define screen layout (assuming a standard 1080p or larger)
# 4 windows in a 2x2 grid
WIDTH=800
HEIGHT=500

POSITIONS=(
    "0,0"       # Top Left
    "850,0"     # Top Right
    "0,550"     # Bottom Left
    "850,550"   # Bottom Right
)

echo "Opening 4 browser windows in a tiled layout:"
for i in "${!ROLES[@]}"; do
    ROLE="${ROLES[$i]}"
    POS="${POSITIONS[$i]}"
    echo " - $ROLE at position $POS"
    
    ROLE_DIR="$PROFILES_DIR/$ROLE"
    mkdir -p "$ROLE_DIR"
    
    # Launch Chrome
    google-chrome --user-data-dir="$ROLE_DIR" \
                  --window-position=$POS \
                  --window-size=$WIDTH,$HEIGHT \
                  --no-first-run \
                  --no-default-browser-check \
                  "$BASE_URL" & disown
    
    sleep 0.5
done

echo "Done. Windows arranged side-by-side."
