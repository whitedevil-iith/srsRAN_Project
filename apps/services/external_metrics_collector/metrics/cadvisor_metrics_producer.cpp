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

#include "cadvisor_metrics_producer.h"
#include "nlohmann/json.hpp"

using namespace srsran;
using namespace app_services;

void cadvisor_metrics_producer_impl::on_new_report_period()
{
  std::string response = http_client::get(endpoint);
  if (response.empty()) {
    logger.warning("Failed to fetch cAdvisor metrics from endpoint: {}", endpoint);
    return;
  }

  cadvisor_metrics new_metrics = parse_cadvisor_response(response);
  notifier.on_new_metric(cadvisor_metrics_impl(new_metrics));
}

cadvisor_metrics cadvisor_metrics_producer_impl::parse_cadvisor_response(const std::string& response)
{
  cadvisor_metrics metrics;

  try {
    nlohmann::json json_data = nlohmann::json::parse(response);

    // cAdvisor returns a map of container paths to container stats
    for (auto& [container_path, container_data] : json_data.items()) {
      if (!container_data.contains("stats") || container_data["stats"].empty()) {
        continue;
      }

      cadvisor_container_metrics container_metrics;

      // Extract container name from aliases or path
      if (container_data.contains("aliases") && !container_data["aliases"].empty()) {
        container_metrics.container_name = container_data["aliases"][0].get<std::string>();
      } else {
        container_metrics.container_name = container_path;
      }

      // Get the most recent stats entry
      auto& latest_stats = container_data["stats"].back();

      // Extract CPU usage
      if (latest_stats.contains("cpu") && latest_stats["cpu"].contains("usage")) {
        auto& cpu_usage = latest_stats["cpu"]["usage"];
        if (cpu_usage.contains("total") && latest_stats["cpu"].contains("usage_nano_cores")) {
          // Convert nanocores to percentage (assuming 100% = 1 core = 1e9 nanocores)
          container_metrics.cpu_usage_percentage =
              static_cast<double>(latest_stats["cpu"]["usage_nano_cores"].get<uint64_t>()) / 1e7;
        }
      }

      // Extract memory usage
      if (latest_stats.contains("memory")) {
        if (latest_stats["memory"].contains("usage")) {
          container_metrics.memory_usage_bytes = latest_stats["memory"]["usage"].get<uint64_t>();
        }
        if (latest_stats["memory"].contains("working_set")) {
          container_metrics.memory_usage_bytes = latest_stats["memory"]["working_set"].get<uint64_t>();
        }
        if (container_data.contains("spec") && container_data["spec"].contains("memory") &&
            container_data["spec"]["memory"].contains("limit")) {
          container_metrics.memory_limit_bytes = container_data["spec"]["memory"]["limit"].get<uint64_t>();
        }
      }

      // Extract network usage
      if (latest_stats.contains("network")) {
        if (latest_stats["network"].contains("interfaces") && !latest_stats["network"]["interfaces"].empty()) {
          uint64_t total_rx = 0, total_tx = 0;
          for (auto& iface : latest_stats["network"]["interfaces"]) {
            if (iface.contains("rx_bytes")) {
              total_rx += iface["rx_bytes"].get<uint64_t>();
            }
            if (iface.contains("tx_bytes")) {
              total_tx += iface["tx_bytes"].get<uint64_t>();
            }
          }
          container_metrics.network_rx_bytes = total_rx;
          container_metrics.network_tx_bytes = total_tx;
        }
      }

      // Extract filesystem usage
      if (latest_stats.contains("filesystem") && !latest_stats["filesystem"].empty()) {
        for (auto& fs : latest_stats["filesystem"]) {
          if (fs.contains("usage")) {
            container_metrics.filesystem_usage += fs["usage"].get<uint64_t>();
          }
          if (fs.contains("capacity")) {
            container_metrics.filesystem_limit += fs["capacity"].get<uint64_t>();
          }
        }
      }

      metrics.containers.push_back(container_metrics);
    }
  } catch (const nlohmann::json::exception& e) {
    logger.warning("Failed to parse cAdvisor JSON response: {}", e.what());
  }

  return metrics;
}
