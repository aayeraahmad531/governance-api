#!/usr/bin/env bash
set -euo pipefail

echo "=== Pushing AI Governance API to Hugging Face Space ==="
echo "Ensure you have added your Hugging Face Space remote:"
echo "  git remote add hf https://huggingface.co/spaces/<YOUR_HF_USERNAME>/<YOUR_SPACE_NAME>"
echo ""
echo "Pushing main branch to Hugging Face..."
git push hf main:main
