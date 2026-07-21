#!/bin/sh
set -e

# Default: weekdays at 22:00 UTC (after US market close)
CRON_SCHEDULE="${INGESTION_CRON:-0 22 * * 1-5}"

echo "${CRON_SCHEDULE} cd /app/ingestion && /usr/local/bin/python run_ingestion.py >> /var/log/ingestion.log 2>&1" \
  > /etc/cron.d/ingestion

chmod 0644 /etc/cron.d/ingestion
crontab /etc/cron.d/ingestion
touch /var/log/ingestion.log

echo "Ingestion cron scheduled: ${CRON_SCHEDULE}"

if [ "${RUN_ON_STARTUP:-true}" = "true" ]; then
  echo "Running initial ingestion on startup..."
  python run_ingestion.py
fi

exec cron -f
