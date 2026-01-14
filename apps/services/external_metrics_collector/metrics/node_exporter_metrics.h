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

#pragma once

#include "apps/services/metrics/metrics_consumer.h"
#include "apps/services/metrics/metrics_properties.h"
#include "apps/services/metrics/metrics_set.h"
#include "srsran/adt/span.h"
#include "srsran/srslog/logger.h"
#include "srsran/support/executors/task_executor.h"
#include "srsran/support/synchronization/stop_event.h"
#include <string>

namespace srsran {

/// Host metrics from Node Exporter.
/// All counter metrics are converted to gauge/rate metrics (delta/time).
struct node_exporter_metrics {
  double   cpu_usage_percentage         = 0.0;
  uint64_t memory_total_bytes           = 0;
  uint64_t memory_available_bytes       = 0;
  uint64_t memory_used_bytes            = 0;
  double   disk_read_bytes_per_sec      = 0.0;   ///< Disk read rate (bytes/sec), converted from counter
  double   disk_write_bytes_per_sec     = 0.0;   ///< Disk write rate (bytes/sec), converted from counter
  double   network_receive_bytes_per_sec = 0.0;  ///< Network receive rate (bytes/sec), converted from counter
  double   network_transmit_bytes_per_sec = 0.0; ///< Network transmit rate (bytes/sec), converted from counter
  double   load_average_1m              = 0.0;
  double   load_average_5m              = 0.0;
  double   load_average_15m             = 0.0;
  uint64_t filesystem_size_bytes        = 0;
  uint64_t filesystem_avail_bytes       = 0;
};

/// Node Exporter metrics properties.
class node_exporter_metrics_properties_impl : public app_services::metrics_properties
{
public:
  std::string_view name() const override { return "Node Exporter metrics"; }
};

/// Node Exporter metrics set implementation.
class node_exporter_metrics_impl : public app_services::metrics_set
{
  node_exporter_metrics_properties_impl properties;
  node_exporter_metrics                 metrics;

public:
  explicit node_exporter_metrics_impl(const node_exporter_metrics& metrics_) : metrics(metrics_) {}

  // See interface for documentation.
  const app_services::metrics_properties& get_properties() const override { return properties; }

  const node_exporter_metrics& get_metrics() const { return metrics; }
};

/// Callback for the Node Exporter metrics.
inline auto node_exporter_metrics_callback = [](const app_services::metrics_set&      report,
                                               span<app_services::metrics_consumer*> consumers,
                                               task_executor&                        executor,
                                               srslog::basic_logger&                 logger,
                                               stop_event_token                      token) {
  const auto& metric = static_cast<const node_exporter_metrics_impl&>(report);

  if (!executor.defer([metric, consumers, stop_token = std::move(token)]() {
        for (auto& consumer : consumers) {
          consumer->handle_metric(metric);
        }
      })) {
    logger.error("Failed to dispatch the metric '{}'", metric.get_properties().name());
  }
};

} // namespace srsran
