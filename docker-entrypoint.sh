#!/bin/sh
set -e

# Replace environment variables in the nginx configuration template
envsubst '${BACKEND_SERVICE}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# Execute the CMD from the Dockerfile
exec "$@"