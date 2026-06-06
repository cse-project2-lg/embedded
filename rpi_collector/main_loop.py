# IMPORT
import json
from datetime import datetime

import paho.mqtt.client as mqtt

from config import (
    MQTT_HOST,
    MQTT_PORT,
    DEVICE_ID,
    ROOM_ID,
    TOPIC_EVENT_CANDIDATE
)

from preprocessor import (
    ToFPreprocessor,
    CSIPreprocessor,
    process_synced_frame
)

from mqtt_subscriber import (
    start_subscriber,
    receive_frame
)

from window_manager import (
    SlidingWindowManager
)

from feature_extractor import (
    extract_window_features
)

from rule_engine import (
    RuleEngine
)

from event_generator import (
    EventCandidateGenerator
)


def iso_to_ns(
    timestamp_str: str
) -> int:
    """
    ISO8601 Timestamp
        ↓
    Unix Timestamp(ns)
    """

    return int(
        datetime.fromisoformat(
            timestamp_str
        ).timestamp()
        * 1_000_000_000
    )


def create_mqtt_publisher():

    try:

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2
        )

    except AttributeError:

        client = mqtt.Client()

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60
    )

    client.loop_start()

    return client


def main():

    # MQTT PUBLISHER
    publisher = create_mqtt_publisher()

    # MQTT SUBSCRIBER
    start_subscriber()

    # COMPONENTS
    tof_pre = ToFPreprocessor()

    csi_pre = CSIPreprocessor()

    sync_buffer = (
        SlidingWindowManager()
    )

    rule_engine = RuleEngine()

    event_generator = (
        EventCandidateGenerator()
    )

    print(
        "[SYSTEM] Edge Fall Detection Pipeline Start"
    )

    while True:

        try:

            # 1. /preprocess/synced_frame 수신
            frame = receive_frame()

            # 2. 전처리
            processed = process_synced_frame(
                frame,
                tof_pre,
                csi_pre
            )

            # CSI 데이터가 없으면 Skip
            if (
                processed["csiFilteredAmp"]
                is None
            ):
                continue

            # 3. Timestamp 정규화
            timestamp_ns = iso_to_ns(
                processed["timestamp"]
            )

            # 4. Sliding Window Buffer 적재
            sync_buffer.push(
                csi=processed["csiFilteredAmp"],
                tof=processed["tofDistanceMm"],
                pir=processed["pirMotion"],
                ts=timestamp_ns
            )

            # Window Size(7초)가
            # 아직 채워지지 않은 경우 대기
            if not sync_buffer.window_ready():
                continue

            # 5. Window 생성
            (
                csi_window,
                tof_window,
                pir_window,
                ts_window
            ) = sync_buffer.get_window()

            # 6. Feature Extraction
            features = (
                extract_window_features(
                    csi_window,
                    tof_window,
                    pir_window,
                    ts_window
                )
            )

            # 7. Rule-Based 1차 판정
            rule_result = (
                rule_engine.judge(
                    features
                )
            )

            # LOW 위험도는 Skip
            if (
                rule_result[
                    "localRiskLevel"
                ] == "LOW"
            ):
                continue

            # 8. event.candidate 생성
            event_candidate = (
                event_generator.build(

                    features=features,

                    rule_result=rule_result,

                    ts_window=ts_window,

                    device_id=DEVICE_ID,

                    room_id=ROOM_ID,

                    csi_status="AVAILABLE"
                )
            )

            # 9. MQTT Publish
            info = publisher.publish(

                TOPIC_EVENT_CANDIDATE,

                json.dumps(
                    event_candidate
                ),

                qos=1
            )

            print(
                "\n[EVENT CANDIDATE]"
            )

            print(
                json.dumps(
                    event_candidate,
                    indent=2,
                    ensure_ascii=False
                )
            )

        except Exception as exc:

            print(
                f"[ERROR] "
                f"Pipeline processing failed: "
                f"{exc}"
            )

            continue


if __name__ == "__main__":
    main()