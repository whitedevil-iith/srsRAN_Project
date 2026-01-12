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
#include "apps/services/external_metrics_collector/external_metrics_config.h"
#include "apps/services/metrics/metrics_notifier.h"
#include <memory>
#include <vector>

namespace srsran {
namespace app_services {

/// External metrics collector service.
struct external_metrics_collector_service {
  /// Metrics configuration for cAdvisor and Node Exporter.
  std::vector<metrics_config> metrics;
};

/// Builds the external metrics collector service.
external_metrics_collector_service build_external_metrics_collector_service(
    app_services::metrics_notifier&      metrics_notifier,
    const external_metrics_config&       config,
    srslog::basic_logger&                logger);

} // namespace app_services
} // namespace srsran
