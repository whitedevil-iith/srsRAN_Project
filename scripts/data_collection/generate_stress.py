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
Stress Generation Script for O-RAN E2 Nodes

This script generates various types of stresses on containers to simulate
cloud deployment conditions. It supports:
- CPU stress (using stress-ng)
- Memory stress (using stress-ng)
- I/O stress (using stress-ng)
- Network packet loss (using tc)
- Network latency (using tc)
- Network bandwidth limiting (using tc)
- Disk I/O stress (using stress-ng)

In traffic_aware mode, stress is only generated when the traffic pattern
has a positive slope (traffic is increasing). Stress probabilities are
configurable per stress type.

All stress events are tracked in a separate file with timestamps synchronized
with the data collection samples.

Usage:
    python generate_stress.py --scenario traffic_aware --duration 3600 \\
        --containers "srscu0,srscu1,srsdu0" --output-dir ./stress_data \\
        --traffic-pattern "[11.0, 8.1, ...]" --stress-prob-cpu 0.3
"""

import argparse
import csv
import json
import logging
import os
import random
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any

from utils import parse_duration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class StressType(Enum):
    """Types of stresses that can be applied."""

    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    NETWORK_LOSS = "network_loss"
    NETWORK_LATENCY = "network_latency"
    NETWORK_BANDWIDTH = "network_bandwidth"
    DISK = "disk"
    NONE = "none"


class StressEvent:
    """Represents a stress event applied to a container."""

    def __init__(
        self,
        timestamp: float,
        container: str,
        stress_type: StressType,
        quantity: float,
        unit: str,
        duration: float,
        interface: str | None = None,
    ):
        self.timestamp = timestamp
        self.container = container
        self.stress_type = stress_type
        self.quantity = quantity
        self.unit = unit
        self.duration = duration
        self.interface = interface
        self.process: subprocess.Popen | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for CSV output."""
        return {
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "timestamp_unix": self.timestamp,
            "container": self.container,
            "stress_type": self.stress_type.value,
            "quantity": self.quantity,
            "unit": self.unit,
            "duration": self.duration,
            "interface": self.interface or "",
        }


class StressApplicator:
    """Applies various stresses to containers."""

    def __init__(self, docker_exec_timeout: int = 30):
        self.docker_exec_timeout = docker_exec_timeout
        self._active_stresses: list[StressEvent] = []
        self._lock = threading.Lock()

    def _docker_exec(
        self, container: str, command: list[str], background: bool = False
    ) -> subprocess.Popen | None:
        """Execute a command in a Docker container."""
        try:
            docker_cmd = ["docker", "exec"]
            if background:
                docker_cmd.append("-d")
            docker_cmd.extend([container] + command)

            logger.debug(f"Running: {' '.join(docker_cmd)}")

            if background:
                process = subprocess.Popen(
                    docker_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                return process
            else:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.docker_exec_timeout,
                )
                if result.returncode != 0:
                    logger.warning(
                        f"Command failed in {container}: {result.stderr}"
                    )
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"Command timed out in {container}")
            return None
        except Exception as e:
            logger.error(f"Failed to execute command in {container}: {e}")
            return None

    def apply_cpu_stress(
        self, container: str, load_percent: float, duration: float
    ) -> StressEvent:
        """
        Apply CPU stress to a container using stress-ng.

        Args:
            container: Container name
            load_percent: CPU load percentage (0-100)
            duration: Duration in seconds
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.CPU,
            quantity=load_percent,
            unit="percent",
            duration=duration,
        )

        # stress-ng command for CPU stress
        cmd = [
            "stress-ng",
            "--cpu", "1",
            "--cpu-load", str(int(load_percent)),
            "--timeout", f"{int(duration)}s",
            "--quiet",
        ]

        process = self._docker_exec(container, cmd, background=True)
        event.process = process

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied CPU stress to {container}: {load_percent}% for {duration}s"
        )
        return event

    def apply_memory_stress(
        self, container: str, memory_mb: float, duration: float
    ) -> StressEvent:
        """
        Apply memory stress to a container using stress-ng.

        Args:
            container: Container name
            memory_mb: Amount of memory to consume in MB
            duration: Duration in seconds
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.MEMORY,
            quantity=memory_mb,
            unit="MB",
            duration=duration,
        )

        # stress-ng command for memory stress
        cmd = [
            "stress-ng",
            "--vm", "1",
            "--vm-bytes", f"{int(memory_mb)}M",
            "--timeout", f"{int(duration)}s",
            "--quiet",
        ]

        process = self._docker_exec(container, cmd, background=True)
        event.process = process

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied memory stress to {container}: {memory_mb}MB for {duration}s"
        )
        return event

    def apply_io_stress(
        self, container: str, workers: int, duration: float
    ) -> StressEvent:
        """
        Apply I/O stress to a container using stress-ng.

        Args:
            container: Container name
            workers: Number of I/O workers
            duration: Duration in seconds
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.IO,
            quantity=workers,
            unit="workers",
            duration=duration,
        )

        cmd = [
            "stress-ng",
            "--io", str(workers),
            "--timeout", f"{int(duration)}s",
            "--quiet",
        ]

        process = self._docker_exec(container, cmd, background=True)
        event.process = process

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied I/O stress to {container}: {workers} workers for {duration}s"
        )
        return event

    def apply_network_loss(
        self, container: str, loss_percent: float, duration: float, interface: str = "eth0"
    ) -> StressEvent:
        """
        Apply packet loss using tc (traffic control).

        Args:
            container: Container name
            loss_percent: Packet loss percentage (0-100)
            duration: Duration in seconds
            interface: Network interface
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.NETWORK_LOSS,
            quantity=loss_percent,
            unit="percent",
            duration=duration,
            interface=interface,
        )

        # Apply packet loss using tc
        cmd = [
            "tc", "qdisc", "add", "dev", interface,
            "root", "netem", "loss", f"{loss_percent}%",
        ]

        self._docker_exec(container, cmd, background=False)

        # Schedule removal of the rule
        def remove_rule():
            time.sleep(duration)
            remove_cmd = ["tc", "qdisc", "del", "dev", interface, "root"]
            self._docker_exec(container, remove_cmd, background=False)
            logger.info(f"Removed network loss from {container}")

        thread = threading.Thread(target=remove_rule, daemon=True)
        thread.start()

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied network loss to {container}: {loss_percent}% for {duration}s"
        )
        return event

    def apply_network_latency(
        self, container: str, latency_ms: float, duration: float, interface: str = "eth0"
    ) -> StressEvent:
        """
        Apply network latency using tc (traffic control).

        Args:
            container: Container name
            latency_ms: Added latency in milliseconds
            duration: Duration in seconds
            interface: Network interface
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.NETWORK_LATENCY,
            quantity=latency_ms,
            unit="ms",
            duration=duration,
            interface=interface,
        )

        # Apply latency using tc
        cmd = [
            "tc", "qdisc", "add", "dev", interface,
            "root", "netem", "delay", f"{latency_ms}ms",
        ]

        self._docker_exec(container, cmd, background=False)

        # Schedule removal of the rule
        def remove_rule():
            time.sleep(duration)
            remove_cmd = ["tc", "qdisc", "del", "dev", interface, "root"]
            self._docker_exec(container, remove_cmd, background=False)
            logger.info(f"Removed network latency from {container}")

        thread = threading.Thread(target=remove_rule, daemon=True)
        thread.start()

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied network latency to {container}: {latency_ms}ms for {duration}s"
        )
        return event

    def apply_network_bandwidth(
        self, container: str, rate_kbps: float, duration: float, interface: str = "eth0"
    ) -> StressEvent:
        """
        Apply network bandwidth limiting using tc (traffic control).

        Args:
            container: Container name
            rate_kbps: Bandwidth limit in kbps
            duration: Duration in seconds
            interface: Network interface
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.NETWORK_BANDWIDTH,
            quantity=rate_kbps,
            unit="kbps",
            duration=duration,
            interface=interface,
        )

        # Apply bandwidth limit using tc
        cmd = [
            "tc", "qdisc", "add", "dev", interface,
            "root", "tbf", "rate", f"{int(rate_kbps)}kbit",
            "burst", "32kbit", "latency", "400ms",
        ]

        self._docker_exec(container, cmd, background=False)

        # Schedule removal of the rule
        def remove_rule():
            time.sleep(duration)
            remove_cmd = ["tc", "qdisc", "del", "dev", interface, "root"]
            self._docker_exec(container, remove_cmd, background=False)
            logger.info(f"Removed bandwidth limit from {container}")

        thread = threading.Thread(target=remove_rule, daemon=True)
        thread.start()

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied bandwidth limit to {container}: {rate_kbps}kbps for {duration}s"
        )
        return event

    def apply_disk_stress(
        self, container: str, workers: int, duration: float
    ) -> StressEvent:
        """
        Apply disk I/O stress to a container using stress-ng.

        Args:
            container: Container name
            workers: Number of HDD workers
            duration: Duration in seconds
        """
        event = StressEvent(
            timestamp=time.time(),
            container=container,
            stress_type=StressType.DISK,
            quantity=workers,
            unit="workers",
            duration=duration,
        )

        cmd = [
            "stress-ng",
            "--hdd", str(workers),
            "--timeout", f"{int(duration)}s",
            "--quiet",
        ]

        process = self._docker_exec(container, cmd, background=True)
        event.process = process

        with self._lock:
            self._active_stresses.append(event)

        logger.info(
            f"Applied disk stress to {container}: {workers} workers for {duration}s"
        )
        return event

    def cleanup_all(self):
        """Terminate all active stresses."""
        with self._lock:
            for event in self._active_stresses:
                if event.process and event.process.poll() is None:
                    event.process.terminate()
                    try:
                        event.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        event.process.kill()

                # Clean up network rules
                if event.stress_type in [
                    StressType.NETWORK_LOSS,
                    StressType.NETWORK_LATENCY,
                    StressType.NETWORK_BANDWIDTH,
                ]:
                    interface = event.interface or "eth0"
                    remove_cmd = ["tc", "qdisc", "del", "dev", interface, "root"]
                    self._docker_exec(event.container, remove_cmd, background=False)

            self._active_stresses.clear()


class StressTracker:
    """Tracks stress events to a CSV file."""

    def __init__(self, output_file: str):
        self.output_file = output_file
        self._file = open(output_file, "w", newline="")
        self._writer = csv.DictWriter(
            self._file,
            fieldnames=[
                "timestamp",
                "timestamp_unix",
                "container",
                "stress_type",
                "quantity",
                "unit",
                "duration",
                "interface",
            ],
        )
        self._writer.writeheader()

    def record_event(self, event: StressEvent):
        """Record a stress event to the file."""
        self._writer.writerow(event.to_dict())
        self._file.flush()

    def close(self):
        """Close the output file."""
        self._file.close()


class StressProbabilities:
    """Configurable probabilities for each stress type."""

    def __init__(
        self,
        cpu: float = 0.3,
        memory: float = 0.2,
        io: float = 0.15,
        network_loss: float = 0.1,
        network_latency: float = 0.15,
        disk: float = 0.1,
    ):
        self.cpu = cpu
        self.memory = memory
        self.io = io
        self.network_loss = network_loss
        self.network_latency = network_latency
        self.disk = disk

    def normalize(self) -> dict[str, float]:
        """Normalize probabilities to sum to 1.0."""
        total = self.cpu + self.memory + self.io + self.network_loss + self.network_latency + self.disk
        if total == 0:
            return {}
        return {
            "cpu": self.cpu / total,
            "memory": self.memory / total,
            "io": self.io / total,
            "network_loss": self.network_loss / total,
            "network_latency": self.network_latency / total,
            "disk": self.disk / total,
        }


class StressScenario:
    """Defines stress scenarios for testing."""

    @staticmethod
    def _get_traffic_slope(pattern: list[float], slice_index: int) -> float:
        """Get the slope of traffic at given slice index."""
        if slice_index <= 0 or slice_index >= len(pattern):
            return 0.0
        return pattern[slice_index] - pattern[slice_index - 1]

    @staticmethod
    def _is_positive_slope(pattern: list[float], slice_index: int) -> bool:
        """Check if traffic has positive slope at given slice index."""
        return StressScenario._get_traffic_slope(pattern, slice_index) > 0

    @staticmethod
    def traffic_aware_stress(
        applicator: StressApplicator,
        tracker: StressTracker,
        containers: list[str],
        duration: float,
        traffic_pattern: list[float],
        probabilities: StressProbabilities,
        interval_range: tuple[float, float] = (10.0, 60.0),
        stress_duration_range: tuple[float, float] = (5.0, 30.0),
    ) -> None:
        """
        Apply random stresses only during positive traffic slope.

        Stress is only applied when the traffic pattern indicates increasing
        traffic (positive slope). Probabilities for each stress type are configurable.

        Args:
            applicator: StressApplicator instance
            tracker: StressTracker instance
            containers: List of container names
            duration: Total scenario duration
            traffic_pattern: List of traffic values for slope detection
            probabilities: Stress type probabilities
            interval_range: Range for interval between stresses
            stress_duration_range: Range for stress duration
        """
        # Build weighted stress functions based on probabilities
        normalized_probs = probabilities.normalize()
        
        # Validate that we have non-zero probabilities
        if not normalized_probs:
            logger.warning("All stress probabilities are zero, no stresses will be applied")
            return
        
        stress_functions = {
            "cpu": lambda c, d: applicator.apply_cpu_stress(c, random.uniform(20, 80), d),
            "memory": lambda c, d: applicator.apply_memory_stress(c, random.uniform(100, 500), d),
            "io": lambda c, d: applicator.apply_io_stress(c, random.randint(1, 4), d),
            "network_loss": lambda c, d: applicator.apply_network_loss(c, random.uniform(1, 10), d),
            "network_latency": lambda c, d: applicator.apply_network_latency(c, random.uniform(10, 100), d),
            "disk": lambda c, d: applicator.apply_disk_stress(c, random.randint(1, 2), d),
        }

        start_time = time.time()
        stop_event = threading.Event()

        def signal_handler(sig, frame):
            stop_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        num_slices = len(traffic_pattern)
        slice_duration = duration / num_slices if num_slices > 0 else duration

        logger.info(f"Traffic-aware stress generation:")
        logger.info(f"  Traffic pattern: {num_slices} slices")
        logger.info(f"  Slice duration: {slice_duration:.2f}s")
        logger.info(f"  Probabilities: {normalized_probs}")

        while not stop_event.is_set() and (time.time() - start_time) < duration:
            elapsed = time.time() - start_time
            current_slice = int(elapsed / slice_duration) if slice_duration > 0 else 0
            current_slice = min(current_slice, num_slices - 1)

            # Check if traffic has positive slope
            if StressScenario._is_positive_slope(traffic_pattern, current_slice):
                # Select stress type based on probabilities
                stress_types = list(normalized_probs.keys())
                weights = [normalized_probs[t] for t in stress_types]
                
                # Validate weights before calling random.choices
                if stress_types and sum(weights) > 0:
                    selected_type = random.choices(stress_types, weights=weights, k=1)[0]
                    stress_func = stress_functions[selected_type]

                    # Select random container and apply stress
                    container = random.choice(containers)
                    stress_dur = random.uniform(*stress_duration_range)

                    logger.info(
                        f"Slice {current_slice}: Positive slope detected, "
                        f"applying {selected_type} stress to {container}"
                    )

                    event = stress_func(container, stress_dur)
                    tracker.record_event(event)
            else:
                logger.debug(f"Slice {current_slice}: No positive slope, skipping stress")

            # Wait for random interval
            interval = random.uniform(*interval_range)
            stop_event.wait(min(interval, duration - (time.time() - start_time)))

    @staticmethod
    def random_stress(
        applicator: StressApplicator,
        tracker: StressTracker,
        containers: list[str],
        duration: float,
        interval_range: tuple[float, float] = (10.0, 60.0),
        stress_duration_range: tuple[float, float] = (5.0, 30.0),
    ):
        """
        Apply random stresses to containers.

        Args:
            applicator: StressApplicator instance
            tracker: StressTracker instance
            containers: List of container names
            duration: Total scenario duration
            interval_range: Range for interval between stresses
            stress_duration_range: Range for stress duration
        """
        stress_functions = [
            lambda c, d: applicator.apply_cpu_stress(
                c, random.uniform(20, 80), d
            ),
            lambda c, d: applicator.apply_memory_stress(
                c, random.uniform(100, 500), d
            ),
            lambda c, d: applicator.apply_io_stress(
                c, random.randint(1, 4), d
            ),
            lambda c, d: applicator.apply_network_loss(
                c, random.uniform(1, 10), d
            ),
            lambda c, d: applicator.apply_network_latency(
                c, random.uniform(10, 100), d
            ),
            lambda c, d: applicator.apply_disk_stress(
                c, random.randint(1, 2), d
            ),
        ]

        start_time = time.time()
        stop_event = threading.Event()

        def signal_handler(sig, frame):
            stop_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while not stop_event.is_set() and (time.time() - start_time) < duration:
            # Select random container and stress type
            container = random.choice(containers)
            stress_func = random.choice(stress_functions)
            stress_duration = random.uniform(*stress_duration_range)

            # Apply stress
            event = stress_func(container, stress_duration)
            tracker.record_event(event)

            # Wait for random interval
            interval = random.uniform(*interval_range)
            stop_event.wait(min(interval, duration - (time.time() - start_time)))

    @staticmethod
    def sequential_stress(
        applicator: StressApplicator,
        tracker: StressTracker,
        containers: list[str],
        stress_duration: float = 30.0,
        rest_duration: float = 10.0,
    ):
        """
        Apply each type of stress sequentially to all containers.

        Args:
            applicator: StressApplicator instance
            tracker: StressTracker instance
            containers: List of container names
            stress_duration: Duration of each stress
            rest_duration: Rest time between stresses
        """
        stress_methods = [
            ("cpu", lambda c: applicator.apply_cpu_stress(c, 50, stress_duration)),
            ("memory", lambda c: applicator.apply_memory_stress(c, 256, stress_duration)),
            ("io", lambda c: applicator.apply_io_stress(c, 2, stress_duration)),
            ("network_loss", lambda c: applicator.apply_network_loss(c, 5, stress_duration)),
            ("network_latency", lambda c: applicator.apply_network_latency(c, 50, stress_duration)),
            ("disk", lambda c: applicator.apply_disk_stress(c, 1, stress_duration)),
        ]

        for stress_name, stress_func in stress_methods:
            logger.info(f"Applying {stress_name} stress to all containers")

            for container in containers:
                event = stress_func(container)
                tracker.record_event(event)

            # Wait for stress duration plus rest
            time.sleep(stress_duration + rest_duration)


def main():
    parser = argparse.ArgumentParser(
        description="Generate stresses on O-RAN E2 node containers"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["random", "sequential", "traffic_aware", "custom"],
        default="random",
        help="Stress scenario type (default: random). Use 'traffic_aware' for stress only during positive traffic slope",
    )
    parser.add_argument(
        "--duration",
        type=str,
        default="1h",
        help="Total duration (e.g., '1h', '30m', '3600'). Default: 1h",
    )
    parser.add_argument(
        "--containers",
        type=str,
        default="srscu0,srscu1,srsdu0,srsdu1,srsdu2",
        help="Comma-separated list of container names",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./stress_data",
        help="Output directory for stress tracking file",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=10.0,
        help="Minimum interval between random stresses (seconds)",
    )
    parser.add_argument(
        "--max-interval",
        type=float,
        default=60.0,
        help="Maximum interval between random stresses (seconds)",
    )
    parser.add_argument(
        "--min-stress-duration",
        type=float,
        default=5.0,
        help="Minimum stress duration (seconds)",
    )
    parser.add_argument(
        "--max-stress-duration",
        type=float,
        default=30.0,
        help="Maximum stress duration (seconds)",
    )
    # Traffic-aware scenario arguments
    parser.add_argument(
        "--traffic-pattern",
        type=str,
        default=None,
        help="Traffic pattern for slope detection (JSON array). Required for traffic_aware scenario.",
    )
    # Stress probability arguments
    parser.add_argument(
        "--stress-prob-cpu",
        type=float,
        default=0.3,
        help="Probability for CPU stress (0.0-1.0). Default: 0.3",
    )
    parser.add_argument(
        "--stress-prob-memory",
        type=float,
        default=0.2,
        help="Probability for memory stress (0.0-1.0). Default: 0.2",
    )
    parser.add_argument(
        "--stress-prob-io",
        type=float,
        default=0.15,
        help="Probability for I/O stress (0.0-1.0). Default: 0.15",
    )
    parser.add_argument(
        "--stress-prob-network-loss",
        type=float,
        default=0.1,
        help="Probability for network loss stress (0.0-1.0). Default: 0.1",
    )
    parser.add_argument(
        "--stress-prob-network-latency",
        type=float,
        default=0.15,
        help="Probability for network latency stress (0.0-1.0). Default: 0.15",
    )
    parser.add_argument(
        "--stress-prob-disk",
        type=float,
        default=0.1,
        help="Probability for disk stress (0.0-1.0). Default: 0.1",
    )

    args = parser.parse_args()

    # Parse duration
    try:
        duration_seconds = parse_duration(args.duration)
    except ValueError as e:
        logger.error(f"Invalid duration: {e}")
        sys.exit(1)

    # Parse containers
    containers = [c.strip() for c in args.containers.split(",")]

    # Parse traffic pattern if provided
    traffic_pattern = None
    if args.traffic_pattern:
        try:
            traffic_pattern = json.loads(args.traffic_pattern)
            if not isinstance(traffic_pattern, list):
                raise ValueError("Traffic pattern must be a list")
            traffic_pattern = [float(x) for x in traffic_pattern]
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Invalid traffic pattern: {e}")
            sys.exit(1)

    # Validate traffic_aware scenario has traffic pattern
    if args.scenario == "traffic_aware" and not traffic_pattern:
        # Use default pattern
        traffic_pattern = [
            11.0, 8.1, 5.6, 3.6, 2.7, 1.9,
            3.0, 5.0, 7.1, 11.1, 11.2, 11.9,
            12.3, 13.0, 13.1, 12.9, 12.7, 12.4,
            12.2, 12.0, 13.0, 14.0, 15.0, 14.0,
        ]
        logger.info("Using default traffic pattern for traffic_aware scenario")

    # Create stress probabilities
    probabilities = StressProbabilities(
        cpu=args.stress_prob_cpu,
        memory=args.stress_prob_memory,
        io=args.stress_prob_io,
        network_loss=args.stress_prob_network_loss,
        network_latency=args.stress_prob_network_latency,
        disk=args.stress_prob_disk,
    )

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Create tracker and applicator
    output_file = os.path.join(
        args.output_dir,
        f"stress_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
    )
    tracker = StressTracker(output_file)
    applicator = StressApplicator()

    logger.info(f"Starting stress generation:")
    logger.info(f"  Scenario: {args.scenario}")
    logger.info(f"  Duration: {duration_seconds}s")
    logger.info(f"  Containers: {containers}")
    logger.info(f"  Output: {output_file}")
    if args.scenario == "traffic_aware":
        logger.info(f"  Traffic pattern: {len(traffic_pattern)} slices")
        logger.info(f"  Stress probabilities: CPU={args.stress_prob_cpu}, "
                   f"Memory={args.stress_prob_memory}, IO={args.stress_prob_io}, "
                   f"NetLoss={args.stress_prob_network_loss}, "
                   f"NetLatency={args.stress_prob_network_latency}, "
                   f"Disk={args.stress_prob_disk}")

    try:
        if args.scenario == "random":
            StressScenario.random_stress(
                applicator=applicator,
                tracker=tracker,
                containers=containers,
                duration=duration_seconds,
                interval_range=(args.min_interval, args.max_interval),
                stress_duration_range=(args.min_stress_duration, args.max_stress_duration),
            )
        elif args.scenario == "sequential":
            StressScenario.sequential_stress(
                applicator=applicator,
                tracker=tracker,
                containers=containers,
            )
        elif args.scenario == "traffic_aware":
            StressScenario.traffic_aware_stress(
                applicator=applicator,
                tracker=tracker,
                containers=containers,
                duration=duration_seconds,
                traffic_pattern=traffic_pattern,
                probabilities=probabilities,
                interval_range=(args.min_interval, args.max_interval),
                stress_duration_range=(args.min_stress_duration, args.max_stress_duration),
            )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    finally:
        logger.info("Cleaning up stresses...")
        applicator.cleanup_all()
        tracker.close()
        logger.info(f"Stress events saved to: {output_file}")


if __name__ == "__main__":
    main()
