import json

from queue import (
    Queue,
    Full,
    Empty
)

import paho.mqtt.client as mqtt

from config import (
    MQTT_HOST,
    MQTT_PORT,
    TOPIC_SYNCED_FRAME
)


# FRAME QUEUE
# 최대 100개 프레임 유지
frame_queue = Queue(
    maxsize=100
)


# MQTT CALLBACK
def on_connect(
    client,
    userdata,
    flags,
    rc,
    properties=None
):

    if rc == 0:

        print(
            "[MQTT] Connected successfully"
        )

        client.subscribe(
            TOPIC_SYNCED_FRAME
        )

        print(
            f"[MQTT] Subscribed to: "
            f"{TOPIC_SYNCED_FRAME}"
        )

    else:

        error_msgs = {

            1:
                "incorrect protocol version",

            2:
                "invalid client identifier",

            3:
                "server unavailable",

            4:
                "bad username or password",

            5:
                "not authorized"
        }

        print(
            "[MQTT ERROR] "
            f"Connection failed: "
            f"{error_msgs.get(rc, f'unknown error {rc}')}"
        )


def on_message(
    client,
    userdata,
    msg
):

    try:

        decoded = (
            msg.payload.decode(
                "utf-8"
            )
        )

        payload = json.loads(
            decoded
        )

        try:

            frame_queue.put(
                payload,
                block=False
            )

        except Full:

            print(
                "[MQTT WARN] "
                "Frame queue full. "
                "Dropping oldest frame."
            )

            try:

                frame_queue.get_nowait()

            except Empty:

                pass

            frame_queue.put(
                payload,
                block=False
            )

    except UnicodeDecodeError as e:

        print(
            "[MQTT ERROR] "
            f"Invalid UTF-8 payload: "
            f"{e}"
        )

    except json.JSONDecodeError as e:

        print(
            "[MQTT ERROR] "
            f"Invalid JSON: "
            f"{e}"
        )

        print(
            "[MQTT ERROR] "
            f"Payload Preview: "
            f"{msg.payload[:100]}"
        )

    except Exception as e:

        print(
            "[MQTT ERROR] "
            f"Unexpected error: "
            f"{type(e).__name__}: "
            f"{e}"
        )


# START SUBSCRIBER
def start_subscriber():

    try:

        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2
        )

    except AttributeError:

        client = mqtt.Client()

    client.on_connect = (
        on_connect
    )

    client.on_message = (
        on_message
    )

    client.connect(
        MQTT_HOST,
        MQTT_PORT,
        60
    )

    client.loop_start()

    return client


# RECEIVE FRAME
def receive_frame():

    return frame_queue.get()