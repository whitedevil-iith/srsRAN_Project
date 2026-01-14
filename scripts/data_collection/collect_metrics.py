#!/usr/bin/env python3
#
# Copyright 2021-2025 Software Radio Systems Limited
#
# This file is part of srsRAN
#
# srsRAN is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# srsRAN is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# A copy of the GNU Affero General Public License can be found in
# the LICENSE file in the top-level directory of this distribution
# and at http://www.gnu.org/licenses/.
#

"""
Data Collection Script for O-RAN E2 Nodes

This script collects metrics from all E2 nodes (CUs, DUs), including:
- cAdvisor container metrics (prefixed with "cAdvisor_")
- Node Exporter host system metrics (prefixed with "nodeExporter_")
- srsRAN application metrics from all layers (prefixed with "CU_" or "DU_")

All counter metrics are converted to gauge metrics by calculating the rate
(difference of values / difference of timestamps).

Metrics are aggregated (avg, min, max, stddev) instead of per-device/per-interface
to make them host-agnostic.

Data is saved separately for each E2 node with timestamp as the primary key
for time synchronization.

Usage:
    python collect_metrics.py --interval 1 --duration 3600 --output-dir ./data
"""

import argparse
import csv
import json
import logging
import math
import os
import re
import signal
import sys
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import requests
import websocket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def calculate_stats(values: list[float]) -> dict[str, float]:
    """
    Calculate aggregate statistics for a list of values.
    
    Args:
        values: List of numeric values
        
    Returns:
        Dictionary with avg, min, max, and stddev
    """
    if not values:
        return {}
    
    n = len(values)
    avg = sum(values) / n
    min_val = min(values)
    max_val = max(values)
    
    # Calculate standard deviation
    if n > 1:
        variance = sum((x - avg) ** 2 for x in values) / (n - 1)
        stddev = math.sqrt(variance)
    else:
        stddev = 0.0
    
    return {
        "avg": avg,
        "min": min_val,
        "max": max_val,
        "stddev": stddev,
    }


class CounterToGaugeConverter:
    """Converts counter metrics to gauge by calculating rate."""

    def __init__(self):
        self._previous_values: dict[str, tuple[float, float]] = {}

    def convert(self, metric_name: str, value: float, timestamp: float) -> float | None:
        """
        Convert a counter metric to gauge by calculating the rate.

        Args:
            metric_name: Unique identifier for the metric
            value: Current counter value
            timestamp: Current timestamp

        Returns:
            Rate (difference/time_delta) or None if this is the first sample
        """
        if metric_name in self._previous_values:
            prev_value, prev_timestamp = self._previous_values[metric_name]
            time_delta = timestamp - prev_timestamp
            if time_delta > 0:
                rate = (value - prev_value) / time_delta
                self._previous_values[metric_name] = (value, timestamp)
                return rate
        self._previous_values[metric_name] = (value, timestamp)
        return None


class MetricsCollector:
    """Collects metrics from various sources."""

    # Known counter metrics from cAdvisor that need to be converted to gauge
    CADVISOR_COUNTER_METRICS = {
        "container_cpu_usage_seconds_total",
        "container_cpu_user_seconds_total",
        "container_cpu_system_seconds_total",
        "container_network_receive_bytes_total",
        "container_network_transmit_bytes_total",
        "container_network_receive_packets_total",
        "container_network_transmit_packets_total",
        "container_network_receive_errors_total",
        "container_network_transmit_errors_total",
        "container_network_receive_packets_dropped_total",
        "container_network_transmit_packets_dropped_total",
        "container_fs_reads_total",
        "container_fs_writes_total",
        "container_fs_read_seconds_total",
        "container_fs_write_seconds_total",
        "container_fs_reads_bytes_total",
        "container_fs_writes_bytes_total",
        "container_blkio_device_usage_total",
    }

    # Known counter metrics from Node Exporter that need to be converted to gauge
    NODE_EXPORTER_COUNTER_METRICS = {
        "node_cpu_seconds_total",
        "node_disk_read_bytes_total",
        "node_disk_written_bytes_total",
        "node_disk_reads_completed_total",
        "node_disk_writes_completed_total",
        "node_disk_read_time_seconds_total",
        "node_disk_write_time_seconds_total",
        "node_network_receive_bytes_total",
        "node_network_transmit_bytes_total",
        "node_network_receive_packets_total",
        "node_network_transmit_packets_total",
        "node_network_receive_errs_total",
        "node_network_transmit_errs_total",
        "node_network_receive_drop_total",
        "node_network_transmit_drop_total",
        "node_context_switches_total",
        "node_intr_total",
        "node_forks_total",
        "node_softnet_dropped_total",
        "node_softnet_processed_total",
        "node_vmstat_pgfault",
        "node_vmstat_pgmajfault",
        "node_vmstat_pgpgin",
        "node_vmstat_pgpgout",
    }

    # Patterns for metrics that should be aggregated (per-CPU, per-interface, per-device)
    # Pattern format: regex with 'base' group to extract base metric name
    CADVISOR_AGGREGATION_PATTERNS = [
        # CPU metrics (per-cpu aggregation)
        r"(?P<base>container_cpu_[a-zA-Z0-9_]+)_\{.*cpu=.*\}",
        # Network metrics (per-interface aggregation)
        r"(?P<base>container_network_[a-zA-Z0-9_]+)_\{.*interface=.*\}",
        # Filesystem metrics (per-device aggregation)
        r"(?P<base>container_fs_[a-zA-Z0-9_]+)_\{.*device=.*\}",
        # Block I/O metrics (per-device aggregation)
        r"(?P<base>container_blkio_[a-zA-Z0-9_]+)_\{.*device=.*\}",
    ]

    NODE_EXPORTER_AGGREGATION_PATTERNS = [
        # CPU metrics (per-cpu aggregation)
        r"(?P<base>node_cpu_[a-zA-Z0-9_]+)_\{.*cpu=.*\}",
        # Network metrics (per-interface aggregation, exclude virtual interfaces)
        r"(?P<base>node_network_[a-zA-Z0-9_]+)_\{.*device=.*\}",
        # Disk metrics (per-device aggregation)
        r"(?P<base>node_disk_[a-zA-Z0-9_]+)_\{.*device=.*\}",
        # Hardware metrics (per-sensor/fan aggregation)
        r"(?P<base>node_hwmon_[a-zA-Z0-9_]+)_\{.*\}",
        r"(?P<base>node_thermal_[a-zA-Z0-9_]+)_\{.*zone=.*\}",
        r"(?P<base>node_cooling_[a-zA-Z0-9_]+)_\{.*\}",
    ]

    def __init__(
        self,
        cadvisor_url: str,
        node_exporter_url: str,
        srsran_endpoints: dict[str, str],
        interval: float = 1.0,
    ):
        """
        Initialize the metrics collector.

        Args:
            cadvisor_url: URL to cAdvisor metrics endpoint
            node_exporter_url: URL to Node Exporter metrics endpoint
            srsran_endpoints: Dict mapping node name to WebSocket URL
            interval: Collection interval in seconds
        """
        self.cadvisor_url = cadvisor_url
        self.node_exporter_url = node_exporter_url
        self.srsran_endpoints = srsran_endpoints
        self.interval = interval
        self.converter = CounterToGaugeConverter()
        self._stop_event = threading.Event()
        self._ws_connections: dict[str, websocket.WebSocketApp] = {}
        self._latest_srsran_metrics: dict[str, dict] = {}
        self._srsran_lock = threading.Lock()

    def _parse_prometheus_metrics(self, text: str) -> dict[str, Any]:
        """Parse Prometheus text format into a dictionary."""
        metrics = {}
        for line in text.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse metric line: metric_name{labels} value
            try:
                if "{" in line:
                    name_labels, value = line.rsplit(" ", 1)
                    name, labels_str = name_labels.split("{", 1)
                    labels_str = labels_str.rstrip("}")
                    # Parse labels
                    labels = {}
                    for label in labels_str.split(","):
                        if "=" in label:
                            k, v = label.split("=", 1)
                            labels[k.strip()] = v.strip().strip('"')
                    key = f"{name}_{labels}"
                else:
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        value = parts[1]
                        labels = {}
                        key = name
                    else:
                        continue

                metrics[key] = {
                    "name": name if "{" not in line else name_labels.split("{")[0],
                    "labels": labels if "{" in line else {},
                    "value": float(value),
                }
            except (ValueError, IndexError):
                continue

        return metrics

    def _is_counter_metric(self, metric_name: str, source: str) -> bool:
        """Check if a metric is a counter type."""
        if source == "cadvisor":
            return any(
                metric_name.startswith(counter)
                for counter in self.CADVISOR_COUNTER_METRICS
            )
        elif source == "node_exporter":
            return any(
                metric_name.startswith(counter)
                for counter in self.NODE_EXPORTER_COUNTER_METRICS
            )
        return False

    def _should_aggregate_metric(self, key: str, patterns: list[str]) -> tuple[bool, str | None]:
        """
        Check if a metric should be aggregated and return its base name.
        
        Args:
            key: The full metric key (name + labels)
            patterns: List of regex patterns for aggregation
            
        Returns:
            Tuple of (should_aggregate, base_name)
        """
        for pattern in patterns:
            match = re.match(pattern, key)
            if match:
                try:
                    base_name = match.group("base")
                    return True, base_name
                except IndexError:
                    return True, match.group(0)
        return False, None

    def collect_cadvisor_metrics(
        self, container_name: str
    ) -> dict[str, Any]:
        """
        Collect metrics from cAdvisor for a specific container.
        Metrics are prefixed with "cAdvisor_" and aggregated (avg, min, max, stddev)
        for per-CPU, per-interface, and per-device metrics.

        Args:
            container_name: Name of the container to filter metrics for

        Returns:
            Dictionary of metrics with gauge values, properly prefixed and aggregated
        """
        try:
            response = requests.get(f"{self.cadvisor_url}/metrics", timeout=5)
            response.raise_for_status()
            raw_metrics = self._parse_prometheus_metrics(response.text)

            timestamp = time.time()
            raw_values: dict[str, float] = {}
            aggregation_groups: dict[str, list[float]] = defaultdict(list)

            for key, metric_data in raw_metrics.items():
                # Filter by container name if present in labels
                labels = metric_data.get("labels", {})
                if "name" in labels and labels["name"] != container_name:
                    continue
                if "container" in labels and labels["container"] != container_name:
                    continue

                metric_name = metric_data["name"]
                value = metric_data["value"]

                # Convert counter to gauge if needed
                if self._is_counter_metric(metric_name, "cadvisor"):
                    gauge_value = self.converter.convert(
                        f"cAdvisor_{container_name}_{key}", value, timestamp
                    )
                    if gauge_value is None:
                        continue
                    value = gauge_value
                    metric_key = f"{metric_name}_rate"
                else:
                    metric_key = metric_name

                # Check if this metric should be aggregated
                should_agg, base_name = self._should_aggregate_metric(
                    key, self.CADVISOR_AGGREGATION_PATTERNS
                )
                
                if should_agg and base_name:
                    aggregation_groups[base_name].append(value)
                else:
                    raw_values[metric_key] = value

            # Build result with proper prefix and aggregation
            result = {}
            
            # Add aggregated metrics with stats
            for base_name, values in aggregation_groups.items():
                stats = calculate_stats(values)
                for stat_name, stat_value in stats.items():
                    result[f"cAdvisor_{base_name}_{stat_name}"] = stat_value
            
            # Add non-aggregated metrics with prefix
            for key, value in raw_values.items():
                result[f"cAdvisor_{key}"] = value

            return result

        except requests.RequestException as e:
            logger.warning(f"Failed to collect cAdvisor metrics: {e}")
            return {}

    def collect_node_exporter_metrics(self) -> dict[str, Any]:
        """
        Collect metrics from Node Exporter.
        Metrics are prefixed with "nodeExporter_" and aggregated (avg, min, max, stddev)
        for per-CPU, per-interface, per-device, and per-sensor metrics.

        Returns:
            Dictionary of metrics with gauge values, properly prefixed and aggregated
        """
        try:
            response = requests.get(f"{self.node_exporter_url}/metrics", timeout=5)
            response.raise_for_status()
            raw_metrics = self._parse_prometheus_metrics(response.text)

            timestamp = time.time()
            raw_values: dict[str, float] = {}
            aggregation_groups: dict[str, list[float]] = defaultdict(list)

            for key, metric_data in raw_metrics.items():
                metric_name = metric_data["name"]
                value = metric_data["value"]

                # Convert counter to gauge if needed
                if self._is_counter_metric(metric_name, "node_exporter"):
                    gauge_value = self.converter.convert(
                        f"NodeExporter_{key}", value, timestamp
                    )
                    if gauge_value is None:
                        continue
                    value = gauge_value
                    metric_key = f"{metric_name}_rate"
                else:
                    metric_key = metric_name

                # Check if this metric should be aggregated
                should_agg, base_name = self._should_aggregate_metric(
                    key, self.NODE_EXPORTER_AGGREGATION_PATTERNS
                )
                
                if should_agg and base_name:
                    aggregation_groups[base_name].append(value)
                else:
                    raw_values[metric_key] = value

            # Build result with proper prefix and aggregation
            result = {}
            
            # Add aggregated metrics with stats
            for base_name, values in aggregation_groups.items():
                stats = calculate_stats(values)
                for stat_name, stat_value in stats.items():
                    result[f"NodeExporter_{base_name}_{stat_name}"] = stat_value
            
            # Add non-aggregated metrics with prefix
            for key, value in raw_values.items():
                result[f"NodeExporter_{key}"] = value

            return result

        except requests.RequestException as e:
            logger.warning(f"Failed to collect Node Exporter metrics: {e}")
            return {}

    def _on_srsran_message(self, node_name: str, message: str):
        """Handle incoming srsRAN WebSocket message."""
        try:
            data = json.loads(message)
            if "cmd" not in data:  # Ignore command responses
                with self._srsran_lock:
                    self._latest_srsran_metrics[node_name] = data
        except json.JSONDecodeError:
            pass

    def _start_srsran_websocket(self, node_name: str, ws_url: str):
        """Start WebSocket connection for srsRAN metrics."""

        def on_open(ws):
            ws.send(json.dumps({"cmd": "metrics_subscribe"}))
            logger.info(f"Connected to srsRAN WebSocket for {node_name}")

        def on_message(ws, message):
            self._on_srsran_message(node_name, message)

        def on_error(ws, error):
            logger.warning(f"WebSocket error for {node_name}: {error}")

        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket closed for {node_name}")

        ws = websocket.WebSocketApp(
            f"ws://{ws_url}",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        self._ws_connections[node_name] = ws

        thread = threading.Thread(target=ws.run_forever, daemon=True)
        thread.start()

    def get_srsran_metrics(self, node_name: str) -> dict[str, Any]:
        """Get the latest srsRAN metrics for a node."""
        with self._srsran_lock:
            return self._latest_srsran_metrics.get(node_name, {}).copy()

    def start_srsran_collection(self):
        """Start WebSocket connections for all srsRAN endpoints."""
        for node_name, ws_url in self.srsran_endpoints.items():
            self._start_srsran_websocket(node_name, ws_url)

    def stop(self):
        """Stop all collection activities."""
        self._stop_event.set()
        for ws in self._ws_connections.values():
            ws.close()


class DataWriter:
    """Writes collected metrics to CSV files."""

    def __init__(self, output_dir: str):
        """
        Initialize the data writer.

        Args:
            output_dir: Directory to write output files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._files: dict[str, Any] = {}
        self._writers: dict[str, csv.DictWriter] = {}
        self._headers_written: dict[str, set] = {}

    def write_sample(
        self, node_name: str, timestamp: float, metrics: dict[str, Any]
    ):
        """
        Write a sample to the node's CSV file.

        Args:
            node_name: Name of the E2 node
            timestamp: Unix timestamp of the sample
            metrics: Dictionary of metric values
        """
        if not metrics:
            return

        # Flatten nested metrics
        flat_metrics = self._flatten_dict(metrics)
        flat_metrics["timestamp"] = datetime.fromtimestamp(timestamp).isoformat()
        flat_metrics["timestamp_unix"] = timestamp

        filename = os.path.join(self.output_dir, f"{node_name}_metrics.csv")

        # Check if we need to create/update the file
        if node_name not in self._files:
            self._files[node_name] = open(filename, "w", newline="")
            self._headers_written[node_name] = set()

        current_headers = set(flat_metrics.keys())

        # If headers changed, recreate the file with new headers
        if not self._headers_written[node_name]:
            self._headers_written[node_name] = current_headers
            headers = ["timestamp", "timestamp_unix"] + sorted(
                [h for h in current_headers if h not in ["timestamp", "timestamp_unix"]]
            )
            self._writers[node_name] = csv.DictWriter(
                self._files[node_name], fieldnames=headers, extrasaction="ignore"
            )
            self._writers[node_name].writeheader()
        elif current_headers - self._headers_written[node_name]:
            # New columns detected - we'll just add what we can
            new_headers = current_headers - self._headers_written[node_name]
            logger.debug(f"New metrics detected for {node_name}: {new_headers}")
            # Update headers set but continue with existing writer
            self._headers_written[node_name].update(current_headers)

        self._writers[node_name].writerow(flat_metrics)
        self._files[node_name].flush()

    def _flatten_dict(
        self, d: dict, parent_key: str = "", sep: str = "_"
    ) -> dict[str, Any]:
        """Flatten a nested dictionary."""
        items: list[tuple[str, Any]] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, dict):
                        items.extend(
                            self._flatten_dict(item, f"{new_key}_{i}", sep).items()
                        )
                    else:
                        items.append((f"{new_key}_{i}", item))
            else:
                items.append((new_key, v))
        return dict(items)

    def close(self):
        """Close all open files."""
        for f in self._files.values():
            f.close()


def parse_e2_nodes(nodes_str: str) -> dict[str, dict[str, str]]:
    """
    Parse E2 nodes configuration string.

    Format: "node_name:container_name:ws_url,node_name2:container_name2:ws_url2"

    Returns:
        Dictionary mapping node names to their configuration
    """
    nodes = {}
    for node in nodes_str.split(","):
        parts = node.strip().split(":")
        if len(parts) >= 3:
            name = parts[0]
            container = parts[1]
            ws_url = ":".join(parts[2:])  # Handle URL with port
            nodes[name] = {"container": container, "ws_url": ws_url}
    return nodes


def get_ran_prefix(node_name: str) -> str:
    """
    Determine the appropriate RAN prefix based on node name.
    
    All RAN metrics are prefixed with "RAN_" regardless of whether
    they come from a CU or DU node.
    
    Args:
        node_name: The E2 node name (e.g., "cu0", "du1")
        
    Returns:
        "RAN_" for all RAN nodes
    """
    return "RAN_"


def prefix_dict_keys(d: dict[str, Any], prefix: str) -> dict[str, Any]:
    """
    Add a prefix to all dictionary keys.
    
    Args:
        d: Dictionary to prefix
        prefix: Prefix to add to each key
        
    Returns:
        New dictionary with prefixed keys
    """
    return {f"{prefix}{k}": v for k, v in d.items()}


def main():
    parser = argparse.ArgumentParser(
        description="Collect metrics from O-RAN E2 nodes"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Collection interval in seconds (default: 1)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Collection duration in seconds (default: run indefinitely)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./collected_data",
        help="Output directory for CSV files (default: ./collected_data)",
    )
    parser.add_argument(
        "--cadvisor-url",
        type=str,
        default="http://localhost:8080",
        help="cAdvisor base URL (default: http://localhost:8080)",
    )
    parser.add_argument(
        "--node-exporter-url",
        type=str,
        default="http://localhost:9100",
        help="Node Exporter base URL (default: http://localhost:9100)",
    )
    parser.add_argument(
        "--e2-nodes",
        type=str,
        default="cu0:srscu0:175.53.10.1:8001,cu1:srscu1:175.53.10.2:8001,"
        "du0:srsdu0:175.53.1.10:8001,du1:srsdu1:175.53.1.13:8001,"
        "du2:srsdu2:175.53.1.14:8001",
        help="E2 nodes configuration (format: name:container:ws_url,...)",
    )
    parser.add_argument(
        "--collect-node-exporter",
        action="store_true",
        default=True,
        help="Collect Node Exporter metrics (default: True)",
    )
    parser.add_argument(
        "--no-collect-node-exporter",
        action="store_false",
        dest="collect_node_exporter",
        help="Disable Node Exporter metrics collection",
    )

    args = parser.parse_args()

    # Parse E2 nodes configuration
    e2_nodes = parse_e2_nodes(args.e2_nodes)

    logger.info(f"Starting data collection with interval={args.interval}s")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"E2 nodes: {list(e2_nodes.keys())}")

    # Create srsRAN endpoints dict
    srsran_endpoints = {name: config["ws_url"] for name, config in e2_nodes.items()}

    # Initialize collector and writer
    collector = MetricsCollector(
        cadvisor_url=args.cadvisor_url,
        node_exporter_url=args.node_exporter_url,
        srsran_endpoints=srsran_endpoints,
        interval=args.interval,
    )

    writer = DataWriter(args.output_dir)

    # Start srsRAN WebSocket collection
    collector.start_srsran_collection()

    # Handle graceful shutdown
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, stopping collection...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Main collection loop
    start_time = time.time()
    sample_count = 0

    try:
        while not stop_event.is_set():
            loop_start = time.time()
            timestamp = loop_start

            # Collect Node Exporter metrics (shared across all nodes)
            node_exporter_metrics = {}
            if args.collect_node_exporter:
                node_exporter_metrics = collector.collect_node_exporter_metrics()

            # Collect metrics for each E2 node
            for node_name, config in e2_nodes.items():
                container_name = config["container"]

                # Collect cAdvisor metrics for this container (already prefixed with cAdvisor_)
                cadvisor_metrics = collector.collect_cadvisor_metrics(container_name)

                # Get srsRAN metrics for this node and prefix with CU_ or DU_
                srsran_metrics = collector.get_srsran_metrics(node_name)
                ran_prefix = get_ran_prefix(node_name)
                prefixed_srsran_metrics = prefix_dict_keys(srsran_metrics, ran_prefix)

                # Combine all metrics (flatten structure, no nested dicts)
                combined_metrics = {}
                
                # Add cAdvisor metrics (already prefixed)
                combined_metrics.update(cadvisor_metrics)
                
                # Add RAN metrics (prefixed with CU_ or DU_)
                combined_metrics.update(prefixed_srsran_metrics)

                # Add node exporter metrics (already prefixed with nodeExporter_)
                if node_exporter_metrics:
                    combined_metrics.update(node_exporter_metrics)

                # Write sample
                writer.write_sample(node_name, timestamp, combined_metrics)

            sample_count += 1

            if sample_count % 60 == 0:
                logger.info(f"Collected {sample_count} samples")

            # Check duration limit
            if args.duration and (time.time() - start_time) >= args.duration:
                logger.info(f"Duration limit reached ({args.duration}s), stopping...")
                break

            # Sleep for remaining interval
            elapsed = time.time() - loop_start
            sleep_time = max(0, args.interval - elapsed)
            if sleep_time > 0:
                stop_event.wait(sleep_time)

    finally:
        collector.stop()
        writer.close()
        logger.info(f"Collection complete. Total samples: {sample_count}")
        logger.info(f"Data saved to: {args.output_dir}")


if __name__ == "__main__":
    main()
