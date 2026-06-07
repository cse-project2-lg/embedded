import logging

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
        try:
            self._write_api.flush()
            self._write_api.close()
            self._client.close()
            logger.info("InfluxDB connection closed.")
        except Exception as exc:
            logger.warning("Failed to close InfluxDB cleanly: %s", exc)