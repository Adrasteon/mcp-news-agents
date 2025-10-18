#!/usr/bin/env bash
# setup_env.sh - Create or update the JustNews MCP agents environment file.
#
# This script interactively collects credentials and connection settings for the
# production PostgreSQL cluster, writing them to a shell-compatible
# EnvironmentFile (suitable for `source` or systemd's `EnvironmentFile=`).
# Existing files are preserved unless the user confirms an overwrite.

set -euo pipefail

DEFAULT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/justnews"
DEFAULT_FILE="$DEFAULT_DIR/justnews.env"

usage() {
  cat <<'EOF'
Usage: setup_env.sh [-f PATH]

Options:
  -f PATH   Absolute or relative path to the environment file to create/update.
            Defaults to "$XDG_CONFIG_HOME/justnews/justnews.env" or
            "$HOME/.config/justnews/justnews.env".
  -h        Show this help text and exit.
EOF
}

TARGET_FILE=""
while getopts ":f:h" opt; do
  case "$opt" in
    f)
      TARGET_FILE="$OPTARG"
      ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "Unknown option: -$OPTARG" >&2
      usage >&2
      exit 2
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      usage >&2
      exit 2
      ;;
  esac
done
shift $((OPTIND - 1))

if [[ -n "${1-}" ]]; then
  echo "Unexpected positional argument '$1'" >&2
  usage >&2
  exit 2
fi

if [[ -z "$TARGET_FILE" ]]; then
  TARGET_FILE="$DEFAULT_FILE"
fi

TARGET_FILE="$(realpath -m "$TARGET_FILE")"
TARGET_DIR="$(dirname "$TARGET_FILE")"

mkdir -p "$TARGET_DIR"
umask 077

if [[ -f "$TARGET_FILE" ]]; then
  read -r -p "Environment file '$TARGET_FILE' exists. Overwrite? [y/N]: " reply
  reply=${reply:-N}
  if [[ ! "$reply" =~ ^[Yy]$ ]]; then
    echo "Aborting without changes."
    exit 0
  fi
fi

read_with_default() {
  local prompt="$1"
  local default_value="$2"
  local var
  if [[ -n "$default_value" ]]; then
    read -r -p "$prompt [$default_value]: " var || true
    var=${var:-$default_value}
  else
    read -r -p "$prompt: " var || true
  fi
  printf '%s' "$var"
}

escape_shell() {
  printf %s "$1" | sed "s/'/'\\''/g"
}

current_host=${JUSTNEWS_DB_HOST:-localhost}
current_port=${JUSTNEWS_DB_PORT:-5432}
current_name=${JUSTNEWS_DB_NAME:-justnews}
current_user=${JUSTNEWS_DB_USER:-justnews_user}
current_batch=${NEWS_SOURCE_BATCH_SIZE:-5}
current_parallelism=${NEWS_CRAWL_PARALLELISM:-1}
current_timeout=${NEWS_CRAWL_TIMEOUT_SECONDS:-120}
current_max_failures=${NEWS_MAX_SOURCE_FAILURES:-5}
current_embeddings=${NEWS_EMBEDDING_ENABLED:-true}
current_model=${NEWS_EMBEDDING_MODEL:-sentence-transformers/all-mpnet-base-v2}
current_embed_batch=${NEWS_EMBEDDING_BATCH:-8}
current_gpu_fraction=${NEWS_EMBEDDING_GPU_FRACTION:-0.65}

host=$(read_with_default "Database host" "$current_host")
port=$(read_with_default "Database port" "$current_port")
db_name=$(read_with_default "Database name" "$current_name")
db_user=$(read_with_default "Database user" "$current_user")

printf 'Enter JUSTNEWS_DB_PASSWORD (input hidden): '
read -rs db_password
printf '\n'
if [[ -z "$db_password" ]]; then
  echo "JUSTNEWS_DB_PASSWORD cannot be empty." >&2
  exit 1
fi

source_batch=$(read_with_default "Sources per batch" "$current_batch")
parallelism=$(read_with_default "Crawl parallelism" "$current_parallelism")
timeout=$(read_with_default "Crawl timeout (seconds)" "$current_timeout")
max_failures=$(read_with_default "Maximum source failures" "$current_max_failures")
embedding_enabled=$(read_with_default "Enable embeddings?" "$current_embeddings")
embedding_model=$(read_with_default "Embedding model" "$current_model")
embedding_batch=$(read_with_default "Embedding batch size" "$current_embed_batch")
embedding_gpu_fraction=$(read_with_default "Embedding GPU fraction" "$current_gpu_fraction")

if [[ "$embedding_enabled" =~ ^[Yy]$ ]]; then
  embedding_enabled=true
fi
if [[ "$embedding_enabled" =~ ^[Nn]$ ]]; then
  embedding_enabled=false
fi

if ! [[ "$port" =~ ^[0-9]+$ ]]; then
  echo "Database port must be numeric." >&2
  exit 1
fi
if ! [[ "$source_batch" =~ ^[0-9]+$ ]]; then
  echo "Sources per batch must be numeric." >&2
  exit 1
fi
if ! [[ "$parallelism" =~ ^[0-9]+$ ]]; then
  echo "Crawl parallelism must be numeric." >&2
  exit 1
fi
if ! [[ "$timeout" =~ ^[0-9]+$ ]]; then
  echo "Crawl timeout must be numeric." >&2
  exit 1
fi
if ! [[ "$max_failures" =~ ^[0-9]+$ ]]; then
  echo "Maximum source failures must be numeric." >&2
  exit 1
fi

if ! [[ "$embedding_gpu_fraction" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
  echo "Embedding GPU fraction must be a decimal." >&2
  exit 1
fi

if [[ "$embedding_batch" != "" ]] && ! [[ "$embedding_batch" =~ ^[0-9]+$ ]]; then
  echo "Embedding batch size must be numeric." >&2
  exit 1
fi

if [[ "$embedding_batch" == "" ]]; then
  embedding_batch=8
fi

if [[ "$embedding_gpu_fraction" == "" ]]; then
  embedding_gpu_fraction=0.65
fi

escaped_password=$(escape_shell "$db_password")
escaped_host=$(escape_shell "$host")
escaped_db_name=$(escape_shell "$db_name")
escaped_db_user=$(escape_shell "$db_user")
escaped_embedding_model=$(escape_shell "$embedding_model")

TEMP_FILE=$(mktemp)
trap 'rm -f "$TEMP_FILE"' EXIT

{
  echo "# JustNews MCP environment configuration"
  echo "# Generated on $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "JUSTNEWS_DB_HOST='$escaped_host'"
  echo "JUSTNEWS_DB_PORT='$port'"
  echo "JUSTNEWS_DB_NAME='$escaped_db_name'"
  echo "JUSTNEWS_DB_USER='$escaped_db_user'"
  echo "JUSTNEWS_DB_PASSWORD='$escaped_password'"
  echo "NEWS_SOURCE_BATCH_SIZE='$source_batch'"
  echo "NEWS_CRAWL_PARALLELISM='$parallelism'"
  echo "NEWS_CRAWL_TIMEOUT_SECONDS='$timeout'"
  echo "NEWS_MAX_SOURCE_FAILURES='$max_failures'"
  echo "NEWS_EMBEDDING_ENABLED='$embedding_enabled'"
  echo "NEWS_EMBEDDING_MODEL='$escaped_embedding_model'"
  echo "NEWS_EMBEDDING_BATCH='$embedding_batch'"
  echo "NEWS_EMBEDDING_GPU_FRACTION='$embedding_gpu_fraction'"
} > "$TEMP_FILE"

install -m 600 "$TEMP_FILE" "$TARGET_FILE"
trap - EXIT
rm -f "$TEMP_FILE"

cat <<EOF
Environment file created at: $TARGET_FILE

To load it in your shell:
  set -a
  source "$TARGET_FILE"
  set +a

For systemd services, reference it with:
  EnvironmentFile=$TARGET_FILE
EOF
