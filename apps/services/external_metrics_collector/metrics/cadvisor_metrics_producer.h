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
#include <string>

namespace srsran {

/// cAdvisor metrics producer implementation.
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
  cadvisor_metrics parse_cadvisor_response(const std::string& response);

  app_services::metrics_notifier& notifier;
  std::string                     endpoint;
  srslog::basic_logger&           logger;
};

} // namespace srsran
