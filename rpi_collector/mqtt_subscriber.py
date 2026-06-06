import json

from queue import Queue

import paho.mqtt.client as mqtt

from config import (
    MQTT_HOST,
    MQTT_PORT,
    TOPIC_SYNCED_FRAME
)

# FRAME QUEUE
frame_queue = Queue()


# MQTT CALLBACK
def on_connect(
    client,
    userdata,
    flags,
    rc
):

    print(
        f"[MQTT] Connected: {rc}"
    )

    client.subscribe(
        TOPIC_SYNCED_FRAME
    )

    print(
        f"[MQTT] Subscribe: {TOPIC_SYNCED_FRAME}"
    )


def on_message(
    client,
    userdata,
    msg
):

    try:

        payload = json.loads(
            msg.payload.decode()
        )

        frame_queue.put(
            payload
        )

    except Exception as e:

        print(
            "[MQTT ERROR]",
            e
        )


# START SUBSCRIBER
def start_subscriber():

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