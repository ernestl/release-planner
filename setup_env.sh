#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
REQ_FILE="${ROOT_DIR}/requirements.txt"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Error: ${PYTHON_BIN} is not installed or not in PATH." >&2
  exit 1
fi

if [[ ! -f "${REQ_FILE}" ]]; then
  echo "Error: requirements file not found at ${REQ_FILE}" >&2
  exit 1
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
else
  echo "Using existing virtual environment at ${VENV_DIR}"
fi

# Activate the environment for this script run.
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "Installing dependencies from ${REQ_FILE}"
python -m pip install --upgrade pip
pip install -r "${REQ_FILE}"

echo
printf 'Done. To activate later, run:\n  source %q\n' "${VENV_DIR}/bin/activate"
