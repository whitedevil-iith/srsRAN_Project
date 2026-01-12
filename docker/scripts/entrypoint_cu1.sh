#!/bin/bash
# =============================================================================
# Entrypoint Script for CU1 (Central Unit 1)
# =============================================================================
#
# This script is executed before starting the srsRAN CU application.
# Add any initialization or setup commands here.
#

set -e

echo "=== CU1 Entrypoint Script ==="
echo "Starting at $(date)"

# Print environment variables for debugging
echo "CADVISOR_ENDPOINT: ${CADVISOR_ENDPOINT:-not set}"
echo "NODE_EXPORTER_ENDPOINT: ${NODE_EXPORTER_ENDPOINT:-not set}"

# Add any custom initialization here
# For example:
# - Wait for dependencies
# - Set up networking
# - Configure environment

echo "CU1 initialization complete"
