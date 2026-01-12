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

#include "apps/helpers/metrics/metrics_config.h"
#include <string>

namespace srsran {

/// External metrics collector configuration.
struct external_metrics_config {
  /// Enable external metrics collection.
  bool enable_external_metrics = false;
  /// cAdvisor endpoint URL (e.g., "http://localhost:8080/api/v1.3/docker").
  std::string cadvisor_endpoint = "http://localhost:8080/api/v1.3/docker";
  /// Node Exporter endpoint URL (e.g., "http://localhost:9100/metrics").
  std::string node_exporter_endpoint = "http://localhost:9100/metrics";
  /// Metrics consumers configuration.
  app_helpers::metrics_config metrics_consumers_cfg;
};

} // namespace srsran
