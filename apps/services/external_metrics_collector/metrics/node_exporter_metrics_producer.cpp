/*
 *
 * Copyright 2021-2025 Software Radio Systems Limited
 *
 * This file is part of srsRAN.
 *
 * srsRAN is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of
 * the License, or (at your option) any later version.
 *
 * srsRAN is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * A copy of the GNU Affero General Public License can be found in
 * the LICENSE file in the top-level directory of this distribution
 * and at http://www.gnu.org/licenses/.
 *
 */

#include "node_exporter_metrics_producer.h"
#include <regex>
#include <sstream>

using namespace srsran;
using namespace app_services;

void node_exporter_metrics_producer_impl::on_new_report_period()
{
  std::string response = http_client::get(endpoint);
  if (response.empty()) {
    logger.warning("Failed to fetch Node Exporter metrics from endpoint: {}", endpoint);
    return;
  }

  node_exporter_metrics new_metrics = parse_node_exporter_response(response);
  notifier.on_new_metric(node_exporter_metrics_impl(new_metrics));
}

node_exporter_metrics node_exporter_metrics_producer_impl::parse_node_exporter_response(const std::string& response)
{
  node_exporter_metrics metrics;

  // Parse Prometheus text format
  std::istringstream stream(response);
  std::string        line;

  // Regular expression to match metric lines: metric_name{labels} value
  std::regex metric_regex(R"(^([a-zA-Z_:][a-zA-Z0-9_:]*)\{?([^\}]*)\}?\s+([0-9.e+-]+))");

  double cpu_idle_sum = 0.0;
  int    cpu_count    = 0;

  while (std::getline(stream, line)) {
    // Skip comments and empty lines
    if (line.empty() || line[0] == '#') {
      continue;
    }

    std::smatch matches;
    if (std::regex_search(line, matches, metric_regex)) {
      std::string metric_name  = matches[1].str();
      std::string labels       = matches[2].str();
      double      metric_value = std::stod(matches[3].str());

      // Extract memory metrics
      if (metric_name == "node_memory_MemTotal_bytes") {
        metrics.memory_total_bytes = static_cast<uint64_t>(metric_value);
      } else if (metric_name == "node_memory_MemAvailable_bytes") {
        metrics.memory_available_bytes = static_cast<uint64_t>(metric_value);
      } else if (metric_name == "node_memory_MemFree_bytes") {
        if (metrics.memory_available_bytes == 0) {
          metrics.memory_available_bytes = static_cast<uint64_t>(metric_value);
        }
      }
      // Extract CPU metrics (idle time)
      else if (metric_name == "node_cpu_seconds_total" && labels.find("mode=\"idle\"") != std::string::npos) {
        cpu_idle_sum += metric_value;
        cpu_count++;
      }
      // Extract disk I/O metrics
      else if (metric_name == "node_disk_read_bytes_total") {
        metrics.disk_read_bytes += static_cast<uint64_t>(metric_value);
      } else if (metric_name == "node_disk_written_bytes_total") {
        metrics.disk_write_bytes += static_cast<uint64_t>(metric_value);
      }
      // Extract network metrics
      else if (metric_name == "node_network_receive_bytes_total") {
        metrics.network_receive_bytes += static_cast<uint64_t>(metric_value);
      } else if (metric_name == "node_network_transmit_bytes_total") {
        metrics.network_transmit_bytes += static_cast<uint64_t>(metric_value);
      }
      // Extract load average
      else if (metric_name == "node_load1") {
        metrics.load_average_1m = metric_value;
      } else if (metric_name == "node_load5") {
        metrics.load_average_5m = metric_value;
      } else if (metric_name == "node_load15") {
        metrics.load_average_15m = metric_value;
      }
      // Extract filesystem metrics (root filesystem)
      else if (metric_name == "node_filesystem_size_bytes" && labels.find("mountpoint=\"/\"") != std::string::npos) {
        metrics.filesystem_size_bytes = static_cast<uint64_t>(metric_value);
      } else if (metric_name == "node_filesystem_avail_bytes" && labels.find("mountpoint=\"/\"") != std::string::npos) {
        metrics.filesystem_avail_bytes = static_cast<uint64_t>(metric_value);
      }
    }
  }

  // Calculate memory used
  if (metrics.memory_total_bytes > metrics.memory_available_bytes) {
    metrics.memory_used_bytes = metrics.memory_total_bytes - metrics.memory_available_bytes;
  }

  // Note: CPU usage percentage calculation from idle time would require maintaining state
  // between calls to calculate the delta. For simplicity, we'll leave it at 0 for now
  // or it could be calculated as (1 - idle_percentage) if we maintain previous values.

  return metrics;
}
