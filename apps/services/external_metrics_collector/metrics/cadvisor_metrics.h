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
#include <vector>

namespace srsran {

/// Container metrics from cAdvisor.
/// All counter metrics are converted to gauge/rate metrics (delta/time).
struct cadvisor_container_metrics {
  std::string container_name;
  double      cpu_usage_percentage       = 0.0;
  uint64_t    memory_usage_bytes         = 0;
  uint64_t    memory_limit_bytes         = 0;
  double      network_rx_bytes_per_sec   = 0.0;  ///< Network receive rate (bytes/sec), converted from counter
  double      network_tx_bytes_per_sec   = 0.0;  ///< Network transmit rate (bytes/sec), converted from counter
  uint64_t    filesystem_usage           = 0;
  uint64_t    filesystem_limit           = 0;
};

/// Collection of cAdvisor metrics.
struct cadvisor_metrics {
  std::vector<cadvisor_container_metrics> containers;
};

/// cAdvisor metrics properties.
class cadvisor_metrics_properties_impl : public app_services::metrics_properties
{
public:
  std::string_view name() const override { return "cAdvisor metrics"; }
};

/// cAdvisor metrics set implementation.
class cadvisor_metrics_impl : public app_services::metrics_set
{
  cadvisor_metrics_properties_impl properties;
  cadvisor_metrics                 metrics;

public:
  explicit cadvisor_metrics_impl(const cadvisor_metrics& metrics_) : metrics(metrics_) {}

  // See interface for documentation.
  const app_services::metrics_properties& get_properties() const override { return properties; }

  const cadvisor_metrics& get_metrics() const { return metrics; }
};

/// Callback for the cAdvisor metrics.
inline auto cadvisor_metrics_callback = [](const app_services::metrics_set&      report,
                                           span<app_services::metrics_consumer*> consumers,
                                           task_executor&                        executor,
                                           srslog::basic_logger&                 logger,
                                           stop_event_token                      token) {
  const auto& metric = static_cast<const cadvisor_metrics_impl&>(report);

  if (!executor.defer([metric, consumers, stop_token = std::move(token)]() {
        for (auto& consumer : consumers) {
          consumer->handle_metric(metric);
        }
      })) {
    logger.error("Failed to dispatch the metric '{}'", metric.get_properties().name());
  }
};

} // namespace srsran
