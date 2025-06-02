#!/bin/bash

INPUT_DIR="$1"
OUTPUT_DIR="$2"

if [[ -z "$INPUT_DIR" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <input_dir> <output_dir>"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

find "$INPUT_DIR" -type f \( -iname "*.doc" -o -iname "*.docs" -o -iname "*.docx" \) | while read -r file; do
  filename=$(basename "$file")
  stem="${filename%.*}"
  pandoc "$file" -o "$OUTPUT_DIR/$stem.pdf"
  if [[ $? -eq 0 ]]; then
    echo "Converted: $file -> $OUTPUT_DIR/$stem.pdf"
  else
    echo "Failed to convert: $file"
  fi
done