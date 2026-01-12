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

#include "http_client.h"
#include <arpa/inet.h>
#include <cstring>
#include <netdb.h>
#include <regex>
#include <sys/socket.h>
#include <unistd.h>

using namespace srsran;
using namespace app_services;

std::string http_client::get(const std::string& url)
{
  // Parse URL to extract host, port, and path
  std::regex  url_regex(R"(^http://([^:/]+)(?::(\d+))?(/.*)?$)");
  std::smatch matches;

  if (!std::regex_match(url, matches, url_regex)) {
    return "";
  }

  std::string host = matches[1].str();
  int         port = matches[2].matched ? std::stoi(matches[2].str()) : 80;
  std::string path = matches[3].matched ? matches[3].str() : "/";

  // Resolve hostname
  struct addrinfo  hints = {}, *addrs = nullptr;
  hints.ai_family   = AF_UNSPEC;
  hints.ai_socktype = SOCK_STREAM;
  hints.ai_protocol = IPPROTO_TCP;

  if (getaddrinfo(host.c_str(), std::to_string(port).c_str(), &hints, &addrs) != 0) {
    return "";
  }

  // Create socket
  int sock = socket(addrs->ai_family, addrs->ai_socktype, addrs->ai_protocol);
  if (sock < 0) {
    freeaddrinfo(addrs);
    return "";
  }

  // Set timeout
  struct timeval timeout;
  timeout.tv_sec  = 5;
  timeout.tv_usec = 0;
  setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
  setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

  // Connect
  if (connect(sock, addrs->ai_addr, addrs->ai_addrlen) < 0) {
    close(sock);
    freeaddrinfo(addrs);
    return "";
  }
  freeaddrinfo(addrs);

  // Build HTTP request
  std::string request = "GET " + path + " HTTP/1.1\r\n" +
                        "Host: " + host + "\r\n" +
                        "Connection: close\r\n" +
                        "\r\n";

  // Send request
  if (send(sock, request.c_str(), request.length(), 0) < 0) {
    close(sock);
    return "";
  }

  // Read response
  std::string response;
  char        buffer[4096];
  ssize_t     bytes_read;

  while ((bytes_read = recv(sock, buffer, sizeof(buffer) - 1, 0)) > 0) {
    buffer[bytes_read] = '\0';
    response += buffer;
  }

  close(sock);

  if (response.empty()) {
    return "";
  }

  // Extract body from response (after "\r\n\r\n")
  size_t body_pos = response.find("\r\n\r\n");
  if (body_pos == std::string::npos) {
    return "";
  }

  std::string body = response.substr(body_pos + 4);

  // Check for chunked encoding and handle it
  if (response.find("Transfer-Encoding: chunked") != std::string::npos) {
    std::string decoded_body;
    size_t      pos = 0;

    while (pos < body.length()) {
      size_t newline_pos = body.find("\r\n", pos);
      if (newline_pos == std::string::npos)
        break;

      std::string chunk_size_str = body.substr(pos, newline_pos - pos);
      
      // Validate hex string and parse chunk size with error handling
      try {
        // Check if string is empty or has invalid characters
        if (chunk_size_str.empty()) {
          break;
        }
        
        size_t chunk_size = std::stoul(chunk_size_str, nullptr, 16);

        if (chunk_size == 0)
          break;

        pos = newline_pos + 2;
        
        // Ensure we don't read beyond buffer
        if (pos + chunk_size > body.length()) {
          break;
        }
        
        decoded_body += body.substr(pos, chunk_size);
        pos += chunk_size + 2; // Skip chunk data and trailing \r\n
      } catch (const std::exception&) {
        // Invalid chunk size format, return what we have
        break;
      }
    }

    return decoded_body;
  }

  return body;
}
