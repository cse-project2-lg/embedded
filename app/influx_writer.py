import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from influxdb_client import InfluxDBClient, Point, WriteOptions

from app.config import Settings


logger = logging.getLogger(__name__)


class InfluxWriter:
    def __init__(self, settings: Settings):
        self._settings = settings

        if not settings.influx_token:
            raise ValueError("INFLUX_TOKEN is empty. Please set it in .env.")

        if not settings.influx_org:
            raise ValueError("INFLUX_ORG is empty. Please set it in .env.")

        if not settings.influx_bucket:
            raise ValueError("INFLUX_BUCKET is empty. Please set it in .env.")

        self._client = InfluxDBClient(
            url=settings.influx_url,
            token=settings.influx_token,
            org=settings.influx_org,
            timeout=10000,
        )

        self._client.ping()

        self._write_api = self._client.write_api(
            write_options=WriteOptions(
                batch_size=100,
                flush_interval=5000,
                jitter_interval=0,
                retry_interval=1000,
                max_retries=5,
                max_retry_delay=30000,
                exponential_base=2,
            )
        )

    def write_point(self, point: Point) -> None:
        self._write_api.write(
            bucket=self._settings.influx_bucket,
            org=self._settings.influx_org,
            record=point,
        )

    def close(self) -> None:
        flush_success = False
        for attempt in range(3):
            try:
                self._write_api.flush()
                flush_success = True
                break
            except Exception as flush_exc:
                if attempt == 2:
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    backup_path = Path(f"emergency_influx_backup_{ts}_influx_writer.log").resolve()
                    logger.error("Failed to flush InfluxDB buffer after 3 attempts - data may be lost. Emergency backup file path: %s. Error: %s", backup_path, flush_exc)
                else:
                    time.sleep(0.5 * (attempt + 1))

        try:
            self._write_api.close()
        except Exception as api_exc:
            logger.warning("Failed to close write_api cleanly: %s", api_exc)

        try:
            self._client.close()
            logger.info("InfluxDB connection closed.")
        except Exception as client_exc:
            logger.warning("Failed to close InfluxDB client cleanly: %s", client_exc)

        if not flush_success:
            raise RuntimeError("Failed to flush InfluxDB buffer cleanly before shutdown.")