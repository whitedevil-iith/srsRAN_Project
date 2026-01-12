# External Metrics Collector for srsRAN

## Overview

The External Metrics Collector extends srsRAN's metrics server to collect system and container metrics from external monitoring tools:
- **cAdvisor**: Docker container metrics (CPU, memory, network, filesystem)
- **Node Exporter**: Host system metrics (CPU, memory, disk, network, load average)

This integration enables comprehensive monitoring of the RAN stack alongside infrastructure metrics, making it easier to correlate application behavior with system resource usage.

## Architecture

The External Metrics Collector follows srsRAN's existing metrics architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                     Metrics Manager                         │
│  (Periodic Collection & Distribution)                       │
└─────────────────────────────────────────────────────────────┘
                           │
         ┌─────────────────┴─────────────────┐
         │                                   │
    ┌────▼────┐                       ┌──────▼──────┐
    │ cAdvisor│                       │    Node     │
    │ Producer│                       │  Exporter   │
    │         │                       │  Producer   │
    └────┬────┘                       └──────┬──────┘
         │                                   │
         │   HTTP GET                        │  HTTP GET
         │   http://localhost:8080/...       │  http://localhost:9100/metrics
         │                                   │
    ┌────▼────────┐                   ┌─────▼────────┐
    │   cAdvisor  │                   │     Node     │
    │  (Docker)   │                   │   Exporter   │
    └─────────────┘                   └──────────────┘
```

### Components

1. **HTTP Client** (`http_client.cpp/h`)
   - Simple HTTP GET implementation using POSIX sockets
   - 5-second timeout for reliability
   - Handles chunked transfer encoding

2. **Metrics Producers** 
   - `cadvisor_metrics_producer`: Fetches and parses cAdvisor JSON API
   - `node_exporter_metrics_producer`: Fetches and parses Prometheus text format

3. **Metrics Consumers**
   - JSON consumers: Output formatted JSON for remote subscribers
   - Log consumers: Human-readable logging output

4. **Configuration**
   - CLI and YAML configuration support
   - Endpoint URLs are configurable
   - Can enable/disable log and JSON outputs independently

## Configuration

### Command Line Options

```bash
gnb --external_metrics.enable true \
    --external_metrics.cadvisor_endpoint http://localhost:8080/api/v1.3/docker \
    --external_metrics.node_exporter_endpoint http://localhost:9100/metrics \
    --external_metrics.enable_log_metrics true \
    --external_metrics.enable_json_metrics true
```

### YAML Configuration

```yaml
external_metrics:
  enable: true
  cadvisor_endpoint: "http://localhost:8080/api/v1.3/docker"
  node_exporter_endpoint: "http://localhost:9100/metrics"
  enable_log_metrics: true
  enable_json_metrics: true
```

### Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `enable` | Enable external metrics collection | `false` |
| `cadvisor_endpoint` | cAdvisor API endpoint URL | `http://localhost:8080/api/v1.3/docker` |
| `node_exporter_endpoint` | Node Exporter metrics endpoint | `http://localhost:9100/metrics` |
| `enable_log_metrics` | Enable human-readable log output | `false` |
| `enable_json_metrics` | Enable JSON output for remote subscribers | `false` |

## Collected Metrics

### cAdvisor Metrics (Per Container)

| Metric | Type | Description |
|--------|------|-------------|
| `container_name` | string | Container name or ID |
| `cpu_usage_percentage` | double | CPU usage as percentage |
| `memory_usage_bytes` | uint64 | Current memory usage in bytes |
| `memory_limit_bytes` | uint64 | Memory limit in bytes |
| `network_rx_bytes` | uint64 | Network received bytes (cumulative) |
| `network_tx_bytes` | uint64 | Network transmitted bytes (cumulative) |
| `filesystem_usage` | uint64 | Filesystem usage in bytes |
| `filesystem_limit` | uint64 | Filesystem limit in bytes |

### Node Exporter Metrics (Host System)

| Metric | Type | Description |
|--------|------|-------------|
| `cpu_usage_percentage` | double | CPU usage as percentage |
| `memory_total_bytes` | uint64 | Total system memory in bytes |
| `memory_available_bytes` | uint64 | Available memory in bytes |
| `memory_used_bytes` | uint64 | Used memory in bytes |
| `disk_read_bytes` | uint64 | Disk read bytes (cumulative) |
| `disk_write_bytes` | uint64 | Disk write bytes (cumulative) |
| `network_receive_bytes` | uint64 | Network received bytes (cumulative) |
| `network_transmit_bytes` | uint64 | Network transmitted bytes (cumulative) |
| `load_average_1m` | double | System load average (1 minute) |
| `load_average_5m` | double | System load average (5 minutes) |
| `load_average_15m` | double | System load average (15 minutes) |
| `filesystem_size_bytes` | uint64 | Root filesystem size in bytes |
| `filesystem_avail_bytes` | uint64 | Root filesystem available in bytes |

## Setup Instructions

### 1. Deploy cAdvisor

Using Docker:
```bash
docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --volume=/dev/disk/:/dev/disk:ro \
  --publish=8080:8080 \
  --detach=true \
  gcr.io/cadvisor/cadvisor:latest
```

Verify: `curl http://localhost:8080/api/v1.3/docker`

### 2. Deploy Node Exporter

Using Docker:
```bash
docker run -d \
  --name=node_exporter \
  --net="host" \
  --pid="host" \
  -v "/:/host:ro,rslave" \
  --publish=9100:9100 \
  quay.io/prometheus/node-exporter:latest \
  --path.rootfs=/host
```

Verify: `curl http://localhost:9100/metrics`

### 3. Configure srsRAN

Add to your gnb configuration file:
```yaml
external_metrics:
  enable: true
  enable_json_metrics: true
```

### 4. Run and Monitor

```bash
# Start gnb with configuration
./gnb -c config.yml

# Subscribe to metrics via WebSocket
wscat -c ws://localhost:55555
{"cmd": "metrics_subscribe"}
```

## Output Examples

### JSON Output (via WebSocket)

```json
{
  "metric_type": "cadvisor",
  "containers": [
    {
      "container_name": "srsran_gnb",
      "cpu_usage_percentage": 45.2,
      "memory_usage_bytes": 524288000,
      "memory_limit_bytes": 2147483648,
      "network_rx_bytes": 1048576,
      "network_tx_bytes": 2097152,
      "filesystem_usage": 104857600,
      "filesystem_limit": 10737418240
    }
  ]
}
```

```json
{
  "metric_type": "node_exporter",
  "cpu_usage_percentage": 23.5,
  "memory_total_bytes": 16777216000,
  "memory_available_bytes": 8388608000,
  "memory_used_bytes": 8388608000,
  "load_average_1m": 1.25,
  "load_average_5m": 1.15,
  "load_average_15m": 1.05,
  "filesystem_size_bytes": 107374182400,
  "filesystem_avail_bytes": 53687091200
}
```

### Log Output

```
cAdvisor metrics [srsran_gnb]: cpu=45.20%, memory=500.00/2048.00 MB, net_rx=1048576 bytes, net_tx=2097152 bytes
Node Exporter metrics: cpu=23.50%, memory=8000.00/16000.00 MB, load=[1.25, 1.15, 1.05], disk=50.00/100.00 GB
```

## Integration with Existing Monitoring

The External Metrics Collector seamlessly integrates with srsRAN's existing metrics infrastructure:

1. **Remote Control WebSocket**: Metrics are automatically forwarded to subscribed clients
2. **JSON Format**: Compatible with existing log parsers and monitoring tools
3. **Periodic Collection**: Follows the same reporting period as other metrics
4. **Unified Architecture**: Uses the same producer/consumer pattern as internal metrics

## Troubleshooting

### Metrics not appearing

1. Verify cAdvisor/Node Exporter are running:
   ```bash
   curl http://localhost:8080/api/v1.3/docker
   curl http://localhost:9100/metrics
   ```

2. Check srsRAN logs for errors:
   ```
   Failed to fetch cAdvisor metrics from endpoint: http://localhost:8080/api/v1.3/docker
   ```

3. Verify configuration is enabled:
   ```yaml
   external_metrics:
     enable: true  # Must be true!
   ```

### Connection timeouts

- Ensure endpoints are accessible from the gnb process
- Check firewall rules if running in containers
- Verify network connectivity: `ping localhost`

### Empty/incomplete metrics

- Check cAdvisor/Node Exporter versions (use latest stable)
- Verify proper permissions for container monitoring
- Review JSON parsing in logs (warnings indicate parsing issues)

## Performance Considerations

- HTTP requests are non-blocking (run in executor context)
- 5-second timeout prevents hanging on unresponsive endpoints
- Metrics collection follows the same period as internal metrics
- Failed fetches are logged but don't impact application operation

## Future Enhancements

Potential future improvements:
- Support for custom Prometheus exporters
- Configurable metric filtering
- Historical metric aggregation
- Additional authentication mechanisms
- HTTPS support with certificate validation
