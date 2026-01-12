#
# Copyright 2021-2025 Software Radio Systems Limited
#
# This file is part of srsRAN
#
# srsRAN is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# srsRAN is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# A copy of the GNU Affero General Public License can be found in
# the LICENSE file in the top-level directory of this distribution
# and at http://www.gnu.org/licenses/.
#

# =============================================================================
# Dockerfile for srsRAN_4G UE
# =============================================================================
# This builds the srsUE from srsRAN_4G project for use with srsRAN_Project gNB
# https://github.com/srsran/srsRAN_4G
#

ARG OS_VERSION=22.04

FROM ubuntu:${OS_VERSION} AS builder

ARG SRSRAN_4G_VERSION=release_23_11

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libfftw3-dev \
    libmbedtls-dev \
    libboost-program-options-dev \
    libconfig++-dev \
    libsctp-dev \
    libzmq3-dev \
    libpcsclite-dev \
    libgtest-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build srsRAN_4G
WORKDIR /src
RUN git clone --branch ${SRSRAN_4G_VERSION} --depth 1 https://github.com/srsran/srsRAN_4G.git

WORKDIR /src/srsRAN_4G/build
RUN cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_GUI=OFF \
    -DENABLE_UHD=OFF \
    -DENABLE_ZEROMQ=ON \
    && make -j$(nproc) srsue

# =============================================================================
# Runtime image
# =============================================================================
FROM ubuntu:${OS_VERSION} AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libfftw3-3 \
    libmbedtls14 \
    libboost-program-options1.74.0 \
    libconfig++9v5 \
    libsctp1 \
    libzmq5 \
    libpcsclite1 \
    libfftw3-dev \
    libmbedtls-dev \
    libboost-program-options-dev \
    libconfig++-dev \
    libsctp-dev \
    libzmq3-dev \
    iperf3 \
    iproute2 \
    iputils-ping \
    net-tools \
    stress-ng \
    && rm -rf /var/lib/apt/lists/*

# Copy srsUE binary and libraries
COPY --from=builder /src/srsRAN_4G/build/srsue/src/srsue /usr/local/bin/srsue
COPY --from=builder /src/srsRAN_4G/build/lib/src/phy/rf/libsrsran_rf.so* /usr/local/lib/
COPY --from=builder /src/srsRAN_4G/build/lib/src/phy/rf/libsrsran_rf_zmq.so* /usr/local/lib/
COPY --from=builder /src/srsRAN_4G/build/lib/src/common/libsrsran_common.so* /usr/local/lib/
COPY --from=builder /src/srsRAN_4G/build/lib/src/phy/libsrsran_phy.so* /usr/local/lib/

# Update library path
RUN ldconfig

# Create config directory
RUN mkdir -p /config

# Set working directory
WORKDIR /config

# Default command
CMD ["srsue", "/config/ue.conf"]
