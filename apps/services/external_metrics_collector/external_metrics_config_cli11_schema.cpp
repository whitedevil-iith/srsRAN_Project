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

#include "external_metrics_config_cli11_schema.h"
#include "apps/helpers/metrics/metrics_config_cli11_schema.h"
#include "CLI/CLI11.hpp"

using namespace srsran;

void srsran::configure_cli11_with_external_metrics_config_schema(CLI::App&                  app,
                                                                 external_metrics_config& config)
{
  CLI::App* external_metrics_subcmd =
      app.add_subcommand("external_metrics", "External metrics collector configuration");

  external_metrics_subcmd
      ->add_option("--enable",
                   config.enable_external_metrics,
                   "Enable external metrics collection from cAdvisor and Node Exporter")
      ->default_val(config.enable_external_metrics);

  external_metrics_subcmd
      ->add_option("--cadvisor_endpoint", config.cadvisor_endpoint, "cAdvisor endpoint URL for container metrics")
      ->default_val(config.cadvisor_endpoint);

  external_metrics_subcmd
      ->add_option("--node_exporter_endpoint",
                   config.node_exporter_endpoint,
                   "Node Exporter endpoint URL for host metrics")
      ->default_val(config.node_exporter_endpoint);

  // Add metrics consumers configuration
  app_helpers::configure_cli11_with_metrics_consumers_config_schema(*external_metrics_subcmd,
                                                                   config.metrics_consumers_cfg);
}
