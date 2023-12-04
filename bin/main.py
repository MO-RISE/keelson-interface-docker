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
import json
import zenoh
import brefv
from brefv.payloads.primitives_pb2 import TimestampedBytes, TimestampedFloat
from environs import Env
from utils_docker import (
    export_container_info,
    start_container,
    stop_container,
    restart_container,
)

env = Env()
KEELSON_REALM: str = env("KEELSON_REALM")
KEELSON_ENTITY_ID: str = env("KEELSON_ENTITY_ID")
KEELSON_INTERFACE_TYPE: str = env("KEELSON_INTERFACE_TYPE")
KEELSON_INTERFACE_ID: str = env("KEELSON_INTERFACE_ID")
KEELSON_TAG: str = env("KEELSON_INTERFACE_TAG")

LOG_LEVEL = env.log_level("LOG_LEVEL", logging.DEBUG)

# Setup logger
logger = logging.getLogger("keelson-docker-sdk")
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=LOG_LEVEL
)
logging.captureWarnings(True)
warnings.filterwarnings("once")


publisher_config = {
    # "priority": zenoh.Priority.REAL_TIME(),
    "congestion_control": zenoh.CongestionControl.DROP(),
}

# --- Command line argument parsing ---
parser = argparse.ArgumentParser(
    prog="z_queryable", description="zenoh queryable example"
)
parser.add_argument(
    "--mode",
    "-m",
    dest="mode",
    choices=["peer", "client"],
    type=str,
    help="The zenoh session mode.",
)
parser.add_argument(
    "--connect",
    "-e",
    dest="connect",
    metavar="ENDPOINT",
    action="append",
    type=str,
    help="Endpoints to connect to.",
)
parser.add_argument(
    "--listen",
    "-l",
    dest="listen",
    metavar="ENDPOINT",
    action="append",
    type=str,
    help="Endpoints to listen on.",
)
parser.add_argument(
    "--key",
    "-k",
    dest="key",
    default="demo/example/queryable",
    type=str,
    help="The key expression matching queries to reply to.",
)
parser.add_argument(
    "--value",
    "-v",
    dest="value",
    default="Queryable from Python!",
    type=str,
    help="The value to reply to queries.",
)
parser.add_argument(
    "--complete",
    dest="complete",
    default=False,
    action="store_true",
    help="Declare the queryable as complete w.r.t. the key expression.",
)
parser.add_argument(
    "--config",
    "-c",
    dest="config",
    metavar="FILE",
    type=str,
    help="A configuration file.",
)

args = parser.parse_args()
conf = (
    zenoh.Config.from_file(args.config) if args.config is not None else zenoh.Config()
)
if args.mode is not None:
    conf.insert_json5(zenoh.config.MODE_KEY, json.dumps(args.mode))
if args.connect is not None:
    conf.insert_json5(zenoh.config.CONNECT_KEY, json.dumps(args.connect))
if args.listen is not None:
    conf.insert_json5(zenoh.config.LISTEN_KEY, json.dumps(args.listen))
key = args.key
value = args.value
complete = args.complete


# Setting up ZENOH session
session = zenoh.open(conf)


def queryable_callback(query):


    print(
        f">> [Queryable ] Received Query '{query.selector}'"
        + (f" with value: {query.value.payload}" if query.value is not None else "no value")
    )

    print("query", query.value)

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

        query.reply(Sample(key, value))  # REAPLY TO QUERY

    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Failed to send to zenoh")


if __name__ == "__main__":
    try:
        print("Declaring Queryable on '{}'...".format(key))
        queryable = session.declare_queryable(key, queryable_callback, complete)

        while True:
            time.sleep(1)
            # forever loop

    finally:
        session.close()
