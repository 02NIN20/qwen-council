#!/bin/bash
# MCP server launcher for Qwen Council
# OpenCode launches this script which sets the environment correctly
export QWEN_COUNCIL_API_URL="http://47.84.227.185"
export PYTHONPATH="/home/lenincoronel/Overall/alibabahack:$PYTHONPATH"
cd /home/lenincoronel/Overall/alibabahack
exec python3 -u -m backend.mcp_server
