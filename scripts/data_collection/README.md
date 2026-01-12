# O-RAN Data Collection and Stress Testing Scripts

This directory contains scripts for collecting metrics from O-RAN E2 nodes (CUs, DUs) and generating various types of stresses for testing purposes.

## Scripts Overview

### 1. `collect_metrics.py` - Data Collection Script

Collects metrics from all E2 nodes including:
- **cAdvisor** container metrics (CPU, memory, network, disk I/O)
- **Node Exporter** host system metrics
- **srsRAN** application metrics from all layers (via WebSocket)

**Key Features:**
- Configurable collection interval (default: 1 second)
- Automatic conversion of counter metrics to gauge metrics (rate calculation)
- Separate CSV file output for each E2 node
- Timestamp-based synchronization across all samples

**Usage:**
```bash
python collect_metrics.py \
    --interval 1 \
    --duration 3600 \
    --output-dir ./collected_data \
    --cadvisor-url http://localhost:8080 \
    --node-exporter-url http://localhost:9100 \
    --e2-nodes "cu0:srscu0:175.53.10.1:8001,du0:srsdu0:175.53.1.10:8001"
```

**Arguments:**
- `--interval`: Collection interval in seconds (default: 1)
- `--duration`: Collection duration in seconds (default: run indefinitely)
- `--output-dir`: Output directory for CSV files
- `--cadvisor-url`: cAdvisor base URL
- `--node-exporter-url`: Node Exporter base URL
- `--e2-nodes`: E2 nodes configuration (format: name:container:ws_url,...)

### 2. `generate_traffic.py` - Traffic Generation Script

Generates iperf UDP traffic for UEs based on a configurable traffic distribution pattern.

**Key Features:**
- Configurable traffic pattern (array of bandwidth values in Mbps)
- Distributes time slices across the total duration
- Supports multiple UEs
- Logs traffic events with timestamps

**Default 24-hour Traffic Pattern:**
```
[11.0, 8.1, 5.6, 3.6, 2.7, 1.9, 3.0, 5.0, 7.1, 11.1, 11.2, 11.9, 
 12.3, 13.0, 13.1, 12.9, 12.7, 12.4, 12.2, 12.0, 13.0, 14.0, 15.0, 14.0]
```

**Usage:**
```bash
python generate_traffic.py \
    --pattern "[11.0, 8.1, 5.6, 3.6, 2.7, 1.9, 3.0, 5.0, 7.1, 11.1, 11.2, 11.9, 12.3, 13.0, 13.1, 12.9, 12.7, 12.4, 12.2, 12.0, 13.0, 14.0, 15.0, 14.0]" \
    --duration 24h \
    --ue-ips "10.45.0.2,10.45.0.3" \
    --server-ip 10.45.0.1 \
    --output-file ./traffic_log.csv
```

**Arguments:**
- `--pattern`: Traffic pattern as JSON array of bandwidth values (Mbps)
- `--duration`: Total duration (e.g., '24h', '1h', '3600s')
- `--ue-ips`: Comma-separated list of UE IP addresses
- `--server-ip`: IP address of the iperf server
- `--server-port`: Port of the iperf server (default: 5001)
- `--scale`: Scale factor for bandwidth values
- `--output-file`: Output file for traffic log

### 3. `generate_stress.py` - Stress Generation Script

Generates various types of stresses on containers to simulate cloud deployment conditions.

**Supported Stress Types:**
- **CPU stress** (using stress-ng): Configurable CPU load percentage
- **Memory stress** (using stress-ng): Configurable memory consumption
- **I/O stress** (using stress-ng): Configurable number of I/O workers
- **Disk stress** (using stress-ng): Configurable HDD workers
- **Network packet loss** (using tc): Configurable loss percentage
- **Network latency** (using tc): Configurable added latency
- **Network bandwidth limiting** (using tc): Configurable rate limit

**Scenarios:**
- `random`: Applies random stresses at random intervals
- `sequential`: Applies each stress type sequentially to all containers

**Usage:**
```bash
python generate_stress.py \
    --scenario random \
    --duration 1h \
    --containers "srscu0,srscu1,srsdu0,srsdu1,srsdu2" \
    --output-dir ./stress_data \
    --min-interval 10 \
    --max-interval 60 \
    --min-stress-duration 5 \
    --max-stress-duration 30
```

**Arguments:**
- `--scenario`: Stress scenario type (random, sequential, custom)
- `--duration`: Total duration (e.g., '1h', '30m', '3600')
- `--containers`: Comma-separated list of container names
- `--output-dir`: Output directory for stress tracking file
- `--min-interval`: Minimum interval between random stresses (seconds)
- `--max-interval`: Maximum interval between random stresses (seconds)
- `--min-stress-duration`: Minimum stress duration (seconds)
- `--max-stress-duration`: Maximum stress duration (seconds)

**Output:**
The script generates a CSV file with the following columns:
- `timestamp`: ISO format timestamp
- `timestamp_unix`: Unix timestamp (for synchronization)
- `container`: Container name where stress was applied
- `stress_type`: Type of stress (cpu, memory, io, network_loss, etc.)
- `quantity`: Amount/intensity of stress
- `unit`: Unit of the quantity
- `duration`: Duration of the stress in seconds
- `interface`: Network interface (for network stresses)

## Docker Compose Integration

These scripts are integrated into the Docker Compose setup. See:
- `docker/docker-compose.srsue.yml`: Full setup with srsRAN_4G UEs, traffic generator, data collector, and stress generator

## Requirements

```
requests>=2.28.0
websocket-client>=1.4.0
```

Install dependencies:
```bash
pip install -r requirements.txt
```

## Counter to Gauge Conversion

The data collection script automatically converts counter metrics to gauge metrics by calculating the rate:

```
rate = (current_value - previous_value) / time_delta
```

This applies to metrics such as:
- `container_cpu_usage_seconds_total` → rate of CPU usage
- `node_network_receive_bytes_total` → bytes per second
- `container_network_transmit_packets_total` → packets per second

## Timestamp Synchronization

All samples are synchronized using Unix timestamps as the primary key. Each E2 node's data file contains:
- `timestamp`: Human-readable ISO format
- `timestamp_unix`: Unix timestamp for precise synchronization

The stress events file uses the same timestamp format, allowing correlation between:
- Collected metrics
- Applied stresses
- Traffic patterns

## Example: Running a Complete Test

```bash
# Terminal 1: Start data collection
python collect_metrics.py --interval 1 --duration 3600 --output-dir ./data

# Terminal 2: Start stress generation
python generate_stress.py --scenario random --duration 3600 --output-dir ./data

# Terminal 3: Start traffic generation
python generate_traffic.py --use-default-pattern --duration 1h --output-file ./data/traffic.csv
```

## License

Copyright 2021-2025 Software Radio Systems Limited
Licensed under the GNU Affero General Public License v3.0
