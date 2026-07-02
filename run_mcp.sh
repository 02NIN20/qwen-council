#!/bin/bash
# =============================================================================
# Multi-Agent Council — MCP Server Launcher
# =============================================================================
# Usage:
#   Export MULTIAGENT_COUNCIL_API_URL or leave default (http://localhost:8000)
#   Then run: bash run_mcp.sh
#
# For OpenCode / Claude Desktop / Cursor:
#   Add this to your opencode.json (or ~/.config/opencode/opencode.jsonc):
#   {
#     "mcp": {
#       "multiagent-council": {
#         "type": "local",
#         "command": ["bash", "/path/to/multiagent-council/run_mcp.sh"]
#       }
#     }
#   }
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default API URL (change to your deployed instance)
export MULTIAGENT_COUNCIL_API_URL="${MULTIAGENT_COUNCIL_API_URL:-${QWEN_COUNCIL_API_URL:-http://localhost:8000}}"

# Ensure Python can find the backend module
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

echo "Multi-Agent Council MCP Server" >&2
echo "  API: $MULTIAGENT_COUNCIL_API_URL" >&2
echo "  CWD: $SCRIPT_DIR" >&2

exec python3 -u -m backend.mcp_server
