#!/usr/bin/env python3
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

"""
Common utility functions for O-RAN data collection and stress testing scripts.
"""


def parse_duration(duration_str: str) -> float:
    """
    Parse a duration string into seconds.

    Supports formats like: "1h", "30m", "3600s", "1h30m", "86400", "2.5h"

    Args:
        duration_str: Duration string to parse

    Returns:
        Duration in seconds as a float

    Raises:
        ValueError: If the duration string format is invalid
    """
    duration_str = duration_str.strip().lower()

    if not duration_str:
        raise ValueError("Empty duration string")

    # Handle pure numeric input (seconds)
    try:
        return float(duration_str)
    except ValueError:
        pass

    total_seconds = 0.0
    current_num = ""
    valid_units = {"h", "m", "s"}

    for i, char in enumerate(duration_str):
        if char.isdigit() or char == ".":
            current_num += char
        elif char in valid_units:
            if not current_num:
                raise ValueError(
                    f"Invalid duration format: unit '{char}' at position {i} "
                    f"without a preceding number in '{duration_str}'"
                )
            value = float(current_num)
            if char == "h":
                total_seconds += value * 3600
            elif char == "m":
                total_seconds += value * 60
            elif char == "s":
                total_seconds += value
            current_num = ""
        else:
            raise ValueError(
                f"Invalid character '{char}' at position {i} in duration "
                f"string '{duration_str}'. Valid characters are digits, '.', "
                "'h' (hours), 'm' (minutes), 's' (seconds)"
            )

    # Handle trailing number without unit (treated as seconds)
    if current_num:
        total_seconds += float(current_num)

    return total_seconds
