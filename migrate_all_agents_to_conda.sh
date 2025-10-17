#!/bin/bash
# This script migrates each agent/server to use a conda environment for maximum isolation and reliability.
# It creates an environment.yml for each agent, creates the conda env, and installs dependencies.

set -e

AGENT_DIRS=(
  "news-database-server"
  "news-cluster-agent"
  "news-factcheck-agent"
  "news-cleaner-agent"
  "news-admin-client"
  "news-analyzer-agent"
  "news-memory-agent"
  "news-orchestrator-agent"
  "news-editor-agent"
  "news-training-agent"
  "news-research-agent"
)

PYTHON_VERSION=3.12

for agent in "${AGENT_DIRS[@]}"; do
  echo "Migrating $agent to conda..."
  cd "$agent"
  # Generate environment.yml from requirements.txt
  echo "name: ${agent}-env" > environment.yml
  echo "channels:" >> environment.yml
  echo "  - defaults" >> environment.yml
  echo "  - conda-forge" >> environment.yml
  # Add pytorch channel if torch is needed
  NEEDS_TORCH=0
  NEEDS_TRANSFORMERS=0
  if [ -f requirements.txt ]; then
    grep -i '^torch' requirements.txt && NEEDS_TORCH=1
    grep -i '^transformers' requirements.txt && NEEDS_TRANSFORMERS=1
  fi
  CHANNELS="  - defaults\n  - conda-forge"
  if [ "$NEEDS_TORCH" = "1" ]; then
    CHANNELS="$CHANNELS\n  - pytorch"
  fi
  echo -e "$CHANNELS" >> environment.yml
  echo "dependencies:" >> environment.yml
  echo "  - python=${PYTHON_VERSION}" >> environment.yml
  if [ -f requirements.txt ]; then
    while read -r dep; do
      [[ -z "$dep" || "$dep" =~ ^# ]] && continue
      # Don't add torch/transformers to conda deps, will install via pip if needed
      if [[ "$dep" =~ ^torch ]]; then continue; fi
      if [[ "$dep" =~ ^transformers ]]; then continue; fi
      echo "  - $dep" >> environment.yml
    done < requirements.txt
  fi
  # Remove old venv if exists
  if [ -d .venv ]; then
    rm -rf .venv
  fi
  # Remove old conda env if exists
  conda env remove -n "${agent}-env" -y || true
  # Create conda env
  conda env create -f environment.yml || conda env update -f environment.yml
  # Install torch/transformers via pip if needed
  if [ "$NEEDS_TORCH" = "1" ] || [ "$NEEDS_TRANSFORMERS" = "1" ]; then
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${agent}-env"
    if [ "$NEEDS_TORCH" = "1" ]; then
      pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
    fi
    if [ "$NEEDS_TRANSFORMERS" = "1" ]; then
      pip install transformers
    fi
    conda deactivate
  fi
  cd ..
  echo "$agent migrated to conda."
done

echo "All agents have been migrated to isolated conda environments."
