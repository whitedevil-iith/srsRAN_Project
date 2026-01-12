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
Traffic Generation Script for O-RAN UEs

This script generates iperf UDP traffic for UEs based on a configurable
traffic distribution pattern over a given time period.

The traffic pattern is specified as an array of values representing the
target bandwidth (in Mbps) for each time slice. The script distributes
these time slices across the total duration.

Example:
    # Generate traffic with 24 time slices over 24 hours (1 hour per slice)
    python generate_traffic.py --pattern "[11.0, 8.1, 5.6, ...]" --duration 24h

    # Generate traffic with 24 time slices over 1 hour (2.5 minutes per slice)
    python generate_traffic.py --pattern "[11.0, 8.1, 5.6, ...]" --duration 1h

Usage:
    python generate_traffic.py --pattern "[11.0, 8.1, 5.6, 3.6, ...]" \\
        --duration 24h --ue-ips "10.45.0.2,10.45.0.3" --server-ip 10.45.0.1
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class TrafficGenerator:
    """Generates iperf UDP traffic based on a distribution pattern."""

    def __init__(
        self,
        ue_ips: list[str],
        server_ip: str,
        server_port: int = 5001,
        bind_port_start: int = 5100,
    ):
        """
        Initialize the traffic generator.

        Args:
            ue_ips: List of UE IP addresses
            server_ip: IP address of the iperf server
            server_port: Port of the iperf server
            bind_port_start: Starting port for UE binding
        """
        self.ue_ips = ue_ips
        self.server_ip = server_ip
        self.server_port = server_port
        self.bind_port_start = bind_port_start
        self._processes: list[subprocess.Popen] = []
        self._stop_event = threading.Event()

    def _run_iperf_client(
        self,
        ue_ip: str,
        bandwidth_mbps: float,
        duration_seconds: int,
        bind_port: int,
    ) -> subprocess.Popen | None:
        """
        Run iperf client for a UE.

        Args:
            ue_ip: IP address of the UE
            bandwidth_mbps: Target bandwidth in Mbps
            duration_seconds: Duration in seconds
            bind_port: Port to bind on UE side

        Returns:
            Subprocess handle or None if failed
        """
        try:
            # iperf3 command for UDP traffic
            cmd = [
                "iperf3",
                "-c", self.server_ip,
                "-p", str(self.server_port),
                "-u",  # UDP mode
                "-b", f"{bandwidth_mbps}M",  # Target bandwidth
                "-t", str(duration_seconds),  # Duration
                "-B", ue_ip,  # Bind to UE IP
                "--cport", str(bind_port),  # Client port
                "-J",  # JSON output
            ]

            logger.debug(f"Running: {' '.join(cmd)}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return process

        except FileNotFoundError:
            logger.error("iperf3 not found. Please install iperf3.")
            return None
        except Exception as e:
            logger.error(f"Failed to start iperf client: {e}")
            return None

    def generate_traffic(
        self,
        pattern: list[float],
        total_duration_seconds: float,
        output_file: str | None = None,
    ):
        """
        Generate traffic following the specified pattern.

        Args:
            pattern: List of bandwidth values (Mbps) for each time slice
            total_duration_seconds: Total duration in seconds
            output_file: Optional file to log traffic events
        """
        if not pattern:
            logger.error("Empty traffic pattern")
            return

        num_slices = len(pattern)
        slice_duration = total_duration_seconds / num_slices

        logger.info(f"Starting traffic generation:")
        logger.info(f"  Pattern: {num_slices} slices")
        logger.info(f"  Total duration: {total_duration_seconds}s")
        logger.info(f"  Slice duration: {slice_duration}s")
        logger.info(f"  UEs: {self.ue_ips}")
        logger.info(f"  Server: {self.server_ip}:{self.server_port}")

        # Open output file if specified
        output_handle = None
        if output_file:
            output_handle = open(output_file, "w")
            output_handle.write(
                "timestamp,timestamp_unix,slice_index,bandwidth_mbps,"
                "ue_ip,duration_seconds\n"
            )

        start_time = time.time()
        slice_index = 0

        try:
            while not self._stop_event.is_set() and slice_index < num_slices:
                bandwidth = pattern[slice_index]
                slice_start = time.time()
                timestamp = datetime.now().isoformat()

                logger.info(
                    f"Slice {slice_index + 1}/{num_slices}: "
                    f"Bandwidth={bandwidth}Mbps, Duration={slice_duration}s"
                )

                # Start iperf clients for each UE
                slice_processes = []
                for i, ue_ip in enumerate(self.ue_ips):
                    bind_port = self.bind_port_start + i

                    process = self._run_iperf_client(
                        ue_ip=ue_ip,
                        bandwidth_mbps=bandwidth,
                        duration_seconds=int(slice_duration),
                        bind_port=bind_port,
                    )

                    if process:
                        slice_processes.append(process)
                        self._processes.append(process)

                        # Log to output file
                        if output_handle:
                            output_handle.write(
                                f"{timestamp},{slice_start},{slice_index},"
                                f"{bandwidth},{ue_ip},{slice_duration}\n"
                            )
                            output_handle.flush()

                # Wait for slice duration
                elapsed = time.time() - slice_start
                remaining = max(0, slice_duration - elapsed)

                if remaining > 0:
                    self._stop_event.wait(remaining)

                # Clean up slice processes
                for process in slice_processes:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()

                slice_index += 1

        finally:
            if output_handle:
                output_handle.close()

            # Clean up all processes
            self.stop()

        total_time = time.time() - start_time
        logger.info(f"Traffic generation complete. Total time: {total_time:.2f}s")

    def stop(self):
        """Stop all traffic generation."""
        self._stop_event.set()
        for process in self._processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        self._processes.clear()


class TrafficPatternManager:
    """Manages traffic patterns for different scenarios."""

    # Default 24-hour traffic pattern (Mbps)
    DEFAULT_24H_PATTERN = [
        11.0, 8.1, 5.6, 3.6, 2.7, 1.9,  # 00:00-06:00 (night)
        3.0, 5.0, 7.1, 11.1, 11.2, 11.9,  # 06:00-12:00 (morning ramp-up)
        12.3, 13.0, 13.1, 12.9, 12.7, 12.4,  # 12:00-18:00 (peak hours)
        12.2, 12.0, 13.0, 14.0, 15.0, 14.0,  # 18:00-24:00 (evening peak)
    ]

    @staticmethod
    def parse_pattern(pattern_str: str) -> list[float]:
        """Parse a pattern string into a list of floats."""
        try:
            pattern = json.loads(pattern_str)
            if isinstance(pattern, list):
                return [float(x) for x in pattern]
            raise ValueError("Pattern must be a list")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid pattern format: {e}")

    @staticmethod
    def scale_pattern(pattern: list[float], scale: float) -> list[float]:
        """Scale all values in a pattern by a factor."""
        return [x * scale for x in pattern]


def parse_duration(duration_str: str) -> float:
    """
    Parse a duration string into seconds.

    Supports formats like: "1h", "30m", "3600s", "1h30m", "86400"
    """
    duration_str = duration_str.strip().lower()

    if duration_str.isdigit():
        return float(duration_str)

    total_seconds = 0
    current_num = ""

    for char in duration_str:
        if char.isdigit() or char == ".":
            current_num += char
        elif char == "h":
            if current_num:
                total_seconds += float(current_num) * 3600
                current_num = ""
        elif char == "m":
            if current_num:
                total_seconds += float(current_num) * 60
                current_num = ""
        elif char == "s":
            if current_num:
                total_seconds += float(current_num)
                current_num = ""
        else:
            raise ValueError(f"Invalid duration format: {duration_str}")

    if current_num:
        total_seconds += float(current_num)

    return total_seconds


def main():
    parser = argparse.ArgumentParser(
        description="Generate iperf UDP traffic for O-RAN UEs"
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default=None,
        help="Traffic pattern as JSON array of bandwidth values (Mbps). "
        "Example: '[11.0, 8.1, 5.6, ...]'",
    )
    parser.add_argument(
        "--duration",
        type=str,
        default="24h",
        help="Total duration (e.g., '24h', '1h', '3600s', '3600'). Default: 24h",
    )
    parser.add_argument(
        "--ue-ips",
        type=str,
        default="10.45.0.2,10.45.0.3",
        help="Comma-separated list of UE IP addresses. "
        "Default: 10.45.0.2,10.45.0.3",
    )
    parser.add_argument(
        "--server-ip",
        type=str,
        default="10.45.0.1",
        help="IP address of the iperf server. Default: 10.45.0.1",
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=5001,
        help="Port of the iperf server. Default: 5001",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor for bandwidth values. Default: 1.0",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Output file for traffic log (CSV format)",
    )
    parser.add_argument(
        "--use-default-pattern",
        action="store_true",
        help="Use the default 24-hour traffic pattern",
    )

    args = parser.parse_args()

    # Parse duration
    try:
        duration_seconds = parse_duration(args.duration)
    except ValueError as e:
        logger.error(f"Invalid duration: {e}")
        sys.exit(1)

    # Get traffic pattern
    if args.use_default_pattern or args.pattern is None:
        pattern = TrafficPatternManager.DEFAULT_24H_PATTERN
        logger.info("Using default 24-hour traffic pattern")
    else:
        try:
            pattern = TrafficPatternManager.parse_pattern(args.pattern)
        except ValueError as e:
            logger.error(f"Invalid pattern: {e}")
            sys.exit(1)

    # Apply scale factor
    if args.scale != 1.0:
        pattern = TrafficPatternManager.scale_pattern(pattern, args.scale)
        logger.info(f"Scaled pattern by factor {args.scale}")

    # Parse UE IPs
    ue_ips = [ip.strip() for ip in args.ue_ips.split(",")]

    # Create traffic generator
    generator = TrafficGenerator(
        ue_ips=ue_ips,
        server_ip=args.server_ip,
        server_port=args.server_port,
    )

    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, stopping traffic generation...")
        generator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Generate traffic
    generator.generate_traffic(
        pattern=pattern,
        total_duration_seconds=duration_seconds,
        output_file=args.output_file,
    )


if __name__ == "__main__":
    main()
