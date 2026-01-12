#!/bin/bash
# =============================================================================
# Entrypoint Script for CU0 (Central Unit 0)
# =============================================================================
#
# This script is executed before starting the srsRAN CU application.
# Add any initialization or setup commands here.
#

set -e

echo "=== CU0 Entrypoint Script ==="
echo "Starting at $(date)"

# Print environment variables for debugging
echo "CADVISOR_ENDPOINT: ${CADVISOR_ENDPOINT:-not set}"
echo "NODE_EXPORTER_ENDPOINT: ${NODE_EXPORTER_ENDPOINT:-not set}"

# Add any custom initialization here
# For example:
# - Wait for dependencies
# - Set up networking
# - Configure environment

echo "CU0 initialization complete"
