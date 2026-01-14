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

#include "node_exporter_metrics_consumer.h"
#include "nlohmann/json.hpp"
#include "srsran/support/format/fmt_to_c_str.h"

using namespace srsran;

void node_exporter_metrics_consumer_json::handle_metric(const app_services::metrics_set& metric)
{
  const node_exporter_metrics& host_metrics = static_cast<const node_exporter_metrics_impl&>(metric).get_metrics();

  nlohmann::json json_output;
  json_output["metric_type"]                           = "node_exporter";
  json_output["NodeExporter_cpu_usage_percentage"]     = host_metrics.cpu_usage_percentage;
  json_output["NodeExporter_memory_total_bytes"]       = host_metrics.memory_total_bytes;
  json_output["NodeExporter_memory_available_bytes"]   = host_metrics.memory_available_bytes;
  json_output["NodeExporter_memory_used_bytes"]        = host_metrics.memory_used_bytes;
  json_output["NodeExporter_disk_read_bytes_per_sec"]  = host_metrics.disk_read_bytes_per_sec;
  json_output["NodeExporter_disk_write_bytes_per_sec"] = host_metrics.disk_write_bytes_per_sec;
  json_output["NodeExporter_network_receive_bytes_per_sec"]  = host_metrics.network_receive_bytes_per_sec;
  json_output["NodeExporter_network_transmit_bytes_per_sec"] = host_metrics.network_transmit_bytes_per_sec;
  json_output["NodeExporter_load_average_1m"]          = host_metrics.load_average_1m;
  json_output["NodeExporter_load_average_5m"]          = host_metrics.load_average_5m;
  json_output["NodeExporter_load_average_15m"]         = host_metrics.load_average_15m;
  json_output["NodeExporter_filesystem_size_bytes"]    = host_metrics.filesystem_size_bytes;
  json_output["NodeExporter_filesystem_avail_bytes"]   = host_metrics.filesystem_avail_bytes;

  log_chan("{}", json_output.dump(2));
}

void node_exporter_metrics_consumer_log::handle_metric(const app_services::metrics_set& metric)
{
  const node_exporter_metrics& host_metrics = static_cast<const node_exporter_metrics_impl&>(metric).get_metrics();

  static constexpr double BYTES_IN_MB = (1 << 20);
  static constexpr double BYTES_IN_GB = (1 << 30);

  double mem_total_mb = static_cast<double>(host_metrics.memory_total_bytes) / BYTES_IN_MB;
  double mem_used_mb  = static_cast<double>(host_metrics.memory_used_bytes) / BYTES_IN_MB;
  double fs_size_gb   = static_cast<double>(host_metrics.filesystem_size_bytes) / BYTES_IN_GB;
  double fs_avail_gb  = static_cast<double>(host_metrics.filesystem_avail_bytes) / BYTES_IN_GB;

  fmt::memory_buffer buffer;
  fmt::format_to(std::back_inserter(buffer),
                 "NodeExporter metrics: cpu={:.2f}%, memory={:.2f}/{:.2f} MB, load=[{:.2f}, {:.2f}, {:.2f}], "
                 "disk_read={:.2f} B/s, disk_write={:.2f} B/s, net_rx={:.2f} B/s, net_tx={:.2f} B/s, "
                 "disk={:.2f}/{:.2f} GB",
                 host_metrics.cpu_usage_percentage,
                 mem_used_mb,
                 mem_total_mb,
                 host_metrics.load_average_1m,
                 host_metrics.load_average_5m,
                 host_metrics.load_average_15m,
                 host_metrics.disk_read_bytes_per_sec,
                 host_metrics.disk_write_bytes_per_sec,
                 host_metrics.network_receive_bytes_per_sec,
                 host_metrics.network_transmit_bytes_per_sec,
                 fs_avail_gb,
                 fs_size_gb);

  log_chan("{}", to_c_str(buffer));
}
