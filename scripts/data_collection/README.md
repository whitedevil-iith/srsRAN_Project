# O-RAN Data Collection and Stress Testing Scripts

This directory contains scripts for collecting metrics from O-RAN E2 nodes (CUs, DUs) and generating various types of stresses for testing purposes.

## Files Overview

- `collect_metrics.py` - Data collection script
- `generate_traffic.py` - Traffic generation script with aggregate mode
- `generate_stress.py` - Stress generation script with traffic-aware mode
- `utils.py` - Shared utility functions
- `requirements.txt` - Python dependencies

## Topology

The docker-compose.srsue.yml supports the following topology:
- **CU0** → DU0, DU1 (2 DUs, each with 2 UEs = 4 UEs)
- **CU1** → DU2 (1 DU with 2 UEs = 2 UEs)
- **Total**: 2 CUs, 3 DUs, 6 UEs

## Scripts Overview

### 1. `collect_metrics.py` - Data Collection Script

Collects metrics from all E2 nodes including:
- **cAdvisor** container metrics (CPU, memory, network, disk I/O) - prefixed with `cAdvisor_`
- **Node Exporter** host system metrics - prefixed with `NodeExporter_`
- **srsRAN** application metrics from all layers (via WebSocket) - prefixed with `RAN_`

**Key Features:**
- Configurable collection interval (default: 1 second)
- Automatic conversion of counter metrics to gauge metrics (rate calculation)
- All counter metrics converted to delta/rate metrics: `(present_val - past_val) / (present_timestamp - past_timestamp)`
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
- **Aggregate mode**: Pattern specifies total bandwidth, randomly split among UEs
- Distributes time slices across the total duration
- Supports multiple UEs (6 UEs in default configuration)
- Logs traffic events with timestamps

**Default 24-hour Traffic Pattern (Aggregate Mbps):**
```
[11.0, 8.1, 5.6, 3.6, 2.7, 1.9, 3.0, 5.0, 7.1, 11.1, 11.2, 11.9, 
 12.3, 13.0, 13.1, 12.9, 12.7, 12.4, 12.2, 12.0, 13.0, 14.0, 15.0, 14.0]
```

**Usage (Aggregate Mode):**
```bash
python generate_traffic.py \
    --pattern "[11.0, 8.1, 5.6, 3.6, 2.7, 1.9, 3.0, 5.0, 7.1, 11.1, 11.2, 11.9, 12.3, 13.0, 13.1, 12.9, 12.7, 12.4, 12.2, 12.0, 13.0, 14.0, 15.0, 14.0]" \
    --duration 24h \
    --ue-ips "10.45.0.2,10.45.0.3,10.45.0.4,10.45.0.5,10.45.0.6,10.45.0.7" \
    --server-ip 10.45.0.1 \
    --aggregate-mode \
    --output-file ./traffic_log.csv
```

**Arguments:**
- `--pattern`: Traffic pattern as JSON array of bandwidth values (Mbps)
- `--duration`: Total duration (e.g., '24h', '1h', '3600s')
- `--ue-ips`: Comma-separated list of UE IP addresses
- `--server-ip`: IP address of the iperf server
- `--server-port`: Port of the iperf server (default: 5001)
- `--scale`: Scale factor for bandwidth values
- `--aggregate-mode`: Treat pattern as aggregate bandwidth, randomly split among UEs
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
- `traffic_aware`: **Only applies stress during positive traffic slope** (when traffic is increasing)

**Usage (Traffic-Aware Mode):**
```bash
python generate_stress.py \
    --scenario traffic_aware \
    --duration 24h \
    --containers "srscu0,srscu1,srsdu0,srsdu1,srsdu2" \
    --output-dir ./stress_data \
    --traffic-pattern "[11.0, 8.1, 5.6, 3.6, 2.7, 1.9, 3.0, 5.0, 7.1, 11.1, 11.2, 11.9, 12.3, 13.0, 13.1, 12.9, 12.7, 12.4, 12.2, 12.0, 13.0, 14.0, 15.0, 14.0]" \
    --stress-prob-cpu 0.3 \
    --stress-prob-memory 0.2 \
    --stress-prob-io 0.15 \
    --stress-prob-network-loss 0.1 \
    --stress-prob-network-latency 0.15 \
    --stress-prob-disk 0.1
```

**Arguments:**
- `--scenario`: Stress scenario type (random, sequential, traffic_aware, custom)
- `--duration`: Total duration (e.g., '1h', '30m', '3600')
- `--containers`: Comma-separated list of container names
- `--output-dir`: Output directory for stress tracking file
- `--traffic-pattern`: Traffic pattern for slope detection (required for traffic_aware)
- `--stress-prob-cpu`: Probability for CPU stress (0.0-1.0, default: 0.3)
- `--stress-prob-memory`: Probability for memory stress (0.0-1.0, default: 0.2)
- `--stress-prob-io`: Probability for I/O stress (0.0-1.0, default: 0.15)
- `--stress-prob-network-loss`: Probability for network loss (0.0-1.0, default: 0.1)
- `--stress-prob-network-latency`: Probability for network latency (0.0-1.0, default: 0.15)
- `--stress-prob-disk`: Probability for disk stress (0.0-1.0, default: 0.1)

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

# Terminal 2: Start stress generation (traffic-aware mode)
python generate_stress.py --scenario traffic_aware --duration 3600 --output-dir ./data

# Terminal 3: Start traffic generation (aggregate mode)
python generate_traffic.py --use-default-pattern --duration 1h --aggregate-mode --output-file ./data/traffic.csv
```

## License

Copyright 2021-2025 Software Radio Systems Limited
Licensed under the GNU Affero General Public License v3.0
