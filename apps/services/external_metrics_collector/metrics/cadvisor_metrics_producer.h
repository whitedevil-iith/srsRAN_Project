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

#include "apps/services/external_metrics_collector/http_client.h"
#include "apps/services/external_metrics_collector/metrics/cadvisor_metrics.h"
#include "apps/services/metrics/metrics_notifier.h"
#include "apps/services/metrics/metrics_producer.h"
#include "srsran/srslog/srslog.h"
#include <chrono>
#include <map>
#include <string>

namespace srsran {

/// Structure to store previous counter values and timestamp for delta calculation.
struct cadvisor_previous_state {
  uint64_t                                     network_rx_bytes = 0;
  uint64_t                                     network_tx_bytes = 0;
  std::chrono::steady_clock::time_point        timestamp;
  bool                                         is_valid = false;
};

/// cAdvisor metrics producer implementation.
/// Converts counter metrics to gauge metrics by calculating the rate (delta/time).
class cadvisor_metrics_producer_impl : public app_services::metrics_producer
{
public:
  cadvisor_metrics_producer_impl(app_services::metrics_notifier& notifier_, const std::string& endpoint_) :
    notifier(notifier_), endpoint(endpoint_), logger(srslog::fetch_basic_logger("METRICS"))
  {
  }

  void on_new_report_period() override;

private:
  /// Parses cAdvisor JSON response and extracts metrics.
  /// Counter metrics are converted to gauge metrics using previous state.
  cadvisor_metrics parse_cadvisor_response(const std::string& response);

  /// Converts counter value to rate using previous state.
  /// Returns 0.0 if this is the first sample or time delta is zero.
  double convert_counter_to_rate(const std::string& container_name,
                                 const std::string& metric_name,
                                 uint64_t           current_value,
                                 std::chrono::steady_clock::time_point current_time);

  app_services::metrics_notifier& notifier;
  std::string                     endpoint;
  srslog::basic_logger&           logger;

  /// Storage for previous counter values per container.
  std::map<std::string, cadvisor_previous_state> previous_states_;
};

} // namespace srsran
