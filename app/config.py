import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mqtt_broker: str
    mqtt_port: int

    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str

    log_level: str

    sensor_raw_topic: str = "/sensor/raw"
    csi_raw_topic: str = "/csi/raw"


def get_settings() -> Settings:
    return Settings(
        mqtt_broker=os.getenv("MQTT_BROKER", "localhost"),
        mqtt_port=int(os.getenv("MQTT_PORT", "1883")),
        influx_url=os.getenv("INFLUX_URL", "http://localhost:8086"),
        influx_token=os.getenv("INFLUX_TOKEN", ""),
        influx_org=os.getenv("INFLUX_ORG", ""),
        influx_bucket=os.getenv("INFLUX_BUCKET", "fall_detection"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )