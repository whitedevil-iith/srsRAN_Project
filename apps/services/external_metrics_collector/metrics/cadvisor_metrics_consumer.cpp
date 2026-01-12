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

#include "cadvisor_metrics_consumer.h"
#include "nlohmann/json.hpp"
#include "srsran/support/format/fmt_to_c_str.h"

using namespace srsran;

void cadvisor_metrics_consumer_json::handle_metric(const app_services::metrics_set& metric)
{
  const cadvisor_metrics& container_metrics = static_cast<const cadvisor_metrics_impl&>(metric).get_metrics();

  nlohmann::json json_output;
  json_output["metric_type"] = "cadvisor";
  json_output["containers"]  = nlohmann::json::array();

  for (const auto& container : container_metrics.containers) {
    nlohmann::json container_json;
    container_json["container_name"]       = container.container_name;
    container_json["cpu_usage_percentage"] = container.cpu_usage_percentage;
    container_json["memory_usage_bytes"]   = container.memory_usage_bytes;
    container_json["memory_limit_bytes"]   = container.memory_limit_bytes;
    container_json["network_rx_bytes"]     = container.network_rx_bytes;
    container_json["network_tx_bytes"]     = container.network_tx_bytes;
    container_json["filesystem_usage"]     = container.filesystem_usage;
    container_json["filesystem_limit"]     = container.filesystem_limit;

    json_output["containers"].push_back(container_json);
  }

  log_chan("{}", json_output.dump(2));
}

void cadvisor_metrics_consumer_log::handle_metric(const app_services::metrics_set& metric)
{
  const cadvisor_metrics& container_metrics = static_cast<const cadvisor_metrics_impl&>(metric).get_metrics();

  static constexpr double BYTES_IN_MB = (1 << 20);

  for (const auto& container : container_metrics.containers) {
    double mem_usage_mb = static_cast<double>(container.memory_usage_bytes) / BYTES_IN_MB;
    double mem_limit_mb = static_cast<double>(container.memory_limit_bytes) / BYTES_IN_MB;

    fmt::memory_buffer buffer;
    fmt::format_to(std::back_inserter(buffer),
                   "cAdvisor metrics [{}]: cpu={:.2f}%, memory={:.2f}/{:.2f} MB, net_rx={} bytes, net_tx={} bytes",
                   container.container_name,
                   container.cpu_usage_percentage,
                   mem_usage_mb,
                   mem_limit_mb,
                   container.network_rx_bytes,
                   container.network_tx_bytes);

    log_chan("{}", to_c_str(buffer));
  }
}
