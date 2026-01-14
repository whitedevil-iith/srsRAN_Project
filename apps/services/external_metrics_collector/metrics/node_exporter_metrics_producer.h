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
#include "apps/services/external_metrics_collector/metrics/node_exporter_metrics.h"
#include "apps/services/metrics/metrics_notifier.h"
#include "apps/services/metrics/metrics_producer.h"
#include "srsran/srslog/srslog.h"
#include <chrono>
#include <string>

namespace srsran {

/// Structure to store previous counter values and timestamp for delta calculation.
struct node_exporter_previous_state {
  uint64_t                              disk_read_bytes      = 0;
  uint64_t                              disk_write_bytes     = 0;
  uint64_t                              network_receive_bytes = 0;
  uint64_t                              network_transmit_bytes = 0;
  std::chrono::steady_clock::time_point timestamp;
  bool                                  is_valid = false;
};

/// Node Exporter metrics producer implementation.
/// Converts counter metrics to gauge metrics by calculating the rate (delta/time).
class node_exporter_metrics_producer_impl : public app_services::metrics_producer
{
public:
  node_exporter_metrics_producer_impl(app_services::metrics_notifier& notifier_, const std::string& endpoint_) :
    notifier(notifier_), endpoint(endpoint_), logger(srslog::fetch_basic_logger("METRICS"))
  {
  }

  void on_new_report_period() override;

private:
  /// Parses Node Exporter Prometheus format response and extracts metrics.
  /// Counter metrics are converted to gauge metrics using previous state.
  node_exporter_metrics parse_node_exporter_response(const std::string& response);

  app_services::metrics_notifier& notifier;
  std::string                     endpoint;
  srslog::basic_logger&           logger;

  /// Storage for previous counter values.
  node_exporter_previous_state previous_state_;
};

} // namespace srsran
