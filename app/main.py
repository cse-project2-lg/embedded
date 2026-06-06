import logging
import signal
import sys

from app.config import get_settings
from app.influx_writer import InfluxWriter
from app.mqtt_listener import MqttInfluxBridge


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger = logging.getLogger(__name__)
    writer = InfluxWriter(settings)
    bridge = MqttInfluxBridge(settings, writer)

    def shutdown(signum, frame):
        logger.info("Shutdown signal received: %s", signum)
        bridge.stop()
        writer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        bridge.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    finally:
        writer.close()


if __name__ == "__main__":
    main()