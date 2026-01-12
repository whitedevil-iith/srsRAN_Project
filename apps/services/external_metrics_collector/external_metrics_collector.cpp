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

#include "external_metrics_collector.h"
#include "apps/helpers/metrics/metrics_helpers.h"
#include "apps/services/external_metrics_collector/metrics/cadvisor_metrics_consumer.h"
#include "apps/services/external_metrics_collector/metrics/cadvisor_metrics_producer.h"
#include "apps/services/external_metrics_collector/metrics/node_exporter_metrics_consumer.h"
#include "apps/services/external_metrics_collector/metrics/node_exporter_metrics_producer.h"

using namespace srsran;
using namespace app_services;

external_metrics_collector_service
app_services::build_external_metrics_collector_service(app_services::metrics_notifier& metrics_notifier,
                                                       const external_metrics_config&  config,
                                                       srslog::basic_logger&           logger)
{
  external_metrics_collector_service service;

  if (!config.enable_external_metrics) {
    return service;
  }

  // Setup cAdvisor metrics
  {
    app_services::metrics_config& cadvisor_metrics_cfg = service.metrics.emplace_back();
    cadvisor_metrics_cfg.metric_name                   = cadvisor_metrics_properties_impl().name();
    cadvisor_metrics_cfg.callback                      = cadvisor_metrics_callback;
    cadvisor_metrics_cfg.producers.emplace_back(
        std::make_unique<cadvisor_metrics_producer_impl>(metrics_notifier, config.cadvisor_endpoint));

    if (config.metrics_consumers_cfg.enable_log_metrics) {
      cadvisor_metrics_cfg.consumers.push_back(
          std::make_unique<cadvisor_metrics_consumer_log>(app_helpers::fetch_logger_metrics_log_channel()));
    }

    if (config.metrics_consumers_cfg.enable_json_metrics) {
      cadvisor_metrics_cfg.consumers.push_back(
          std::make_unique<cadvisor_metrics_consumer_json>(app_helpers::fetch_json_metrics_log_channel()));
    }
  }

  // Setup Node Exporter metrics
  {
    app_services::metrics_config& node_exporter_metrics_cfg = service.metrics.emplace_back();
    node_exporter_metrics_cfg.metric_name                   = node_exporter_metrics_properties_impl().name();
    node_exporter_metrics_cfg.callback                      = node_exporter_metrics_callback;
    node_exporter_metrics_cfg.producers.emplace_back(
        std::make_unique<node_exporter_metrics_producer_impl>(metrics_notifier, config.node_exporter_endpoint));

    if (config.metrics_consumers_cfg.enable_log_metrics) {
      node_exporter_metrics_cfg.consumers.push_back(
          std::make_unique<node_exporter_metrics_consumer_log>(app_helpers::fetch_logger_metrics_log_channel()));
    }

    if (config.metrics_consumers_cfg.enable_json_metrics) {
      node_exporter_metrics_cfg.consumers.push_back(
          std::make_unique<node_exporter_metrics_consumer_json>(app_helpers::fetch_json_metrics_log_channel()));
    }
  }

  return service;
}
