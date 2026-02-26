#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Example deploy script: build and run with docker-compose
set -e
cd "$(dirname "$0")/.."
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
