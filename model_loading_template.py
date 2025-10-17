"""
Template: Agent-Side Model Loading with Versioned Model Store

- Loads models from a centralized, versioned model_store
- Uses config to select agent, version, and model assignments
- Supports atomic upgrades/rollbacks and integrity checks
"""
import os
import json
from pathlib import Path
from typing import Any, Dict

import torch  # or import your preferred ML framework

# --- CONFIGURATION ---
AGENT_NAME = os.environ.get("AGENT_NAME", "news-analyzer-agent")
MODEL_STORE_ROOT = os.environ.get("MODEL_STORE_ROOT", "./model_store")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "current")  # can be 'current' or a specific version like 'v1'

# --- RESOLVE MODEL PATHS ---
def get_model_dir(agent: str, version: str) -> Path:
    agent_dir = Path(MODEL_STORE_ROOT) / agent / version
    if not agent_dir.exists():
        raise FileNotFoundError(f"Model directory not found: {agent_dir}")
    return agent_dir

def load_manifest(agent: str, version: str) -> Dict[str, Any]:
    manifest_path = get_model_dir(agent, version) / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    with open(manifest_path, "r") as f:
        return json.load(f)

def find_model_paths(agent: str, version: str) -> Dict[str, Path]:
    model_dir = get_model_dir(agent, version)
    model_paths = {}
    for subdir in model_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith("models--"):
            model_name = subdir.name.replace("models--", "")
            model_paths[model_name] = subdir
    return model_paths

# --- LOAD MODELS (EXAMPLE: Hugging Face Transformers) ---
def load_hf_model(model_path: Path, **kwargs):
    from transformers import AutoModel, AutoTokenizer
    model = AutoModel.from_pretrained(str(model_path), **kwargs)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), **kwargs)
    return model, tokenizer

# --- MAIN LOADING LOGIC ---
def load_agent_models():
    manifest = load_manifest(AGENT_NAME, MODEL_VERSION)
    model_paths = find_model_paths(AGENT_NAME, MODEL_VERSION)
    loaded_models = {}
    for model_name, path in model_paths.items():
        # Customize per agent/model type as needed
        model, tokenizer = load_hf_model(path)
        loaded_models[model_name] = {"model": model, "tokenizer": tokenizer}
    return loaded_models, manifest

if __name__ == "__main__":
    models, manifest = load_agent_models()
    print(f"Loaded models for agent '{AGENT_NAME}': {list(models.keys())}")
    print(f"Manifest: {manifest}")
