#!/bin/bash

# Workaround for the first request timing out in podman
wait_seconds=1
echo "Waiting for $wait_seconds seconds..."
sleep $wait_seconds
cd /app
# exec — чтобы python стал PID 1 и получал SIGTERM от docker stop (graceful shutdown)
exec python parser_cls.py
