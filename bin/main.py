#!/usr/bin/env python3

"""
Docker SDK for start, stop and monitoring containers running on platforms with Keelson configured 

"""

import time
import struct
import socket
import logging
import argparse
import warnings

import zenoh
import brefv
from brefv.payloads.primitives_pb2 import TimestampedBytes, TimestampedFloat
from environs import Env
from utils_docker import export_container_info, start_container, stop_container, restart_container

env = Env()
KEELSON_REALM = env("KEELSON_REALM")
KEELSON_ENTITY_ID = env("KEELSON_ENTITY_ID")
KEELSON_INTERFACE_TYPE = "haddock"
KEELSON_INTERFACE_ID = env("KEELSON_INTERFACE_ID")
KEELSON_TAG = "lever_position_pct"

ARDUINO_IDs = {
    2: "arduino/left",
    3: "arduino/right",
}


logger = logging.getLogger("arduino2keelson")


session = zenoh.open()

publisher_config = {
    "priority": zenoh.Priority.REAL_TIME(),
    "congestion_control": zenoh.CongestionControl.DROP(),
}


def generate_source_id(
    msg_id: int, value_id: int = None
):  # pylint: disable=redefined-outer-name
    """
    Generate a specific multi-level source id based on the msg_id and (optionally) value_id
    """
    source_id = ARDUINO_IDs[msg_id]

    if value_id is None:
        return source_id

    match msg_id:
        case 2 | 3:
            mapping = {
                0: "azimuth/horizontal",
                1: "azimuth/vertical",
                2: "knob/right",
                3: "knob/left",
            }
        case _:
            raise KeyError(f"msg_id {msg_id} not supported!")

    if value_id not in mapping:
        raise NotImplementedError(
            f"The combination msg_id={msg_id} and value_id={value_id} is not supported!"
        )

    source_id = f"{source_id}/{mapping[value_id]}"

    return source_id


if __name__ == "__main__":
    
    # Setup logger
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s", level=args.log_level
    )
    logging.captureWarnings(True)
    warnings.filterwarnings("once")

    try:
        while True:
            data, addr = sock.recvfrom(2048)  # buffer size is 1024 bytes
            logger.debug("Received datagram from %s with length %d", addr, len(data))
            ingress_timestamp = time.time_ns()

            # Legacy code
            msg_id = int(data[0])
            count = int(data[1])
            values = struct.unpack(f"xx{count}h", data)

            logging.debug("Decoded values: %s", values)

            # Publishing to zenoh
            try:
                topic = brefv.construct_pub_sub_topic(
                    realm=KEELSON_REALM,
                    entity_id=KEELSON_ENTITY_ID,
                    interface_type=KEELSON_INTERFACE_TYPE,
                    interface_id=KEELSON_INTERFACE_ID,
                    tag="haddock",
                    source_id=generate_source_id(msg_id=msg_id),
                )
                payload = TimestampedBytes()
                payload.timestamp.FromNanoseconds(ingress_timestamp)
                payload.value = data
                message = brefv.enclose(payload.SerializeToString())
                session.put(topic, message, **publisher_config)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception("Failed to send to zenoh")

            for ix, value in enumerate(values):
                try:
                    try:
                        source_id = generate_source_id(msg_id=msg_id, value_id=ix)
                    except NotImplementedError as exc:
                        # No support, lets send a warning to the logs and then continue
                        warnings.warn(str(exc))
                        continue

                    topic = brefv.construct_pub_sub_topic(
                        realm=KEELSON_REALM,
                        entity_id=KEELSON_ENTITY_ID,
                        interface_type=KEELSON_INTERFACE_TYPE,
                        interface_id=KEELSON_INTERFACE_ID,
                        tag="lever_position_pct",
                        source_id=source_id,
                    )
                    payload = TimestampedFloat()
                    payload.timestamp.FromNanoseconds(ingress_timestamp)
                    payload.value = value
                    message = brefv.enclose(payload.SerializeToString())
                    session.put(topic, message, **publisher_config)
                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to send to zenoh")

    finally:
        sock.close()
        session.close()
