from __future__ import annotations

import argparse
import time
from pathlib import Path

from collectors.mock_collector import MockCollector
from collectors.wifall_collector import WiFallCollector
from collectors.hardware_collector import HardwareCollector
from mqtt.publisher import MqttPublisher
from processing.event_builder import EventBuilder
from processing.validator import validate_raw_message
from utils.config_loader import load_config
from utils.logger import setup_logger


def create_collector(mode: str, config, wifall_csv: str | None):
    if mode == "mock":
        return MockCollector(config)
    if mode == "wifall":
        if not wifall_csv:
            raise ValueError("--wifall-csv path is required when mode=wifall")
        return WiFallCollector(config, wifall_csv)
    if mode == "hardware":
        return HardwareCollector(config)
    raise ValueError(f"unsupported mode: {mode}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--mode", choices=["mock", "wifall", "hardware"], default="mock")
    parser.add_argument("--wifall-csv", default=None)
    args = parser.parse_args()

    config = load_config(args.config)
    logger = setup_logger(
        config["logging"]["log_dir"],
        config["logging"]["level"],
    )

    collector = create_collector(args.mode, config, args.wifall_csv)
    publisher = MqttPublisher(config, logger)
    event_builder = EventBuilder(config)

    interval_sec = float(config["collector"]["interval_sec"])

    logger.info("Embedded edge collector started mode=%s", args.mode)

    try:
        publisher.connect()

        publisher.publish("status", {
            "type": "system.status",
            "source": "rpi4-edge",
            "payload": {
                "status": "STARTED",
                "mode": args.mode,
            },
        })

        while True:
            try:
                raw = collector.read()
                valid, errors = validate_raw_message(raw)

                publisher.publish("raw", raw)

                processed = event_builder.build_processed(raw, valid, errors)
                publisher.publish("processed", processed)

                candidate = event_builder.build_candidate_if_needed(processed)
                if candidate:
                    publisher.publish("candidate", candidate)
                    logger.warning("candidate event created: %s", candidate["payload"]["summary"])

                if not valid:
                    publisher.publish("error", {
                        "type": "system.alert",
                        "source": "rpi4-edge",
                        "payload": {
                            "alertType": "DATA_VALIDATION_ERROR",
                            "message": "센서 데이터 검증 실패",
                            "errors": errors,
                        },
                    })

            except NotImplementedError as e:
                logger.error(str(e))
                break
            except Exception as e:
                logger.exception("loop error: %s", e)
                try:
                    publisher.publish("error", {
                        "type": "system.alert",
                        "source": "rpi4-edge",
                        "payload": {
                            "alertType": "COLLECTOR_RUNTIME_ERROR",
                            "message": str(e),
                        },
                    })
                except Exception:
                    pass

            time.sleep(interval_sec)

    except KeyboardInterrupt:
        logger.info("stopped by user")
    finally:
        publisher.close()


if __name__ == "__main__":
    main()
