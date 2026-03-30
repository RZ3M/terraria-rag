#!/usr/bin/env bash
# Runs the full wiki ingestion in the background, logging to SCRIPTS/ingestion.log
cd ~/Documents/Projects/terraria-rag
exec > SCRIPTS/ingestion.log 2>&1
exec python3 -u INGESTION/run_ingestion.py --no-resume
