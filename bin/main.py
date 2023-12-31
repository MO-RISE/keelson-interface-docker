#!/usr/bin/env python3

"""
Docker SDK for start, stop and monitoring containers running on platforms with Keelson configured 

"""

import time
import logging
import argparse
import warnings
import json
import zenoh
from zenoh import config, Sample, Value
import brefv
from brefv.payloads.primitives_pb2 import TimestampedBytes, TimestampedFloat
from environs import Env
from utils_docker import (
    export_container_info,
    start_container,
    stop_container,
    restart_container,
    get_container_logs,
)

env = Env()
KEELSON_REALM: str = env("KEELSON_REALM", "rise")
KEELSON_ENTITY_ID: str = env("KEELSON_ENTITY_ID", "seahorse")
KEELSON_INTERFACE_TYPE: str = env("KEELSON_INTERFACE_TYPE", "docker-sdk")
KEELSON_INTERFACE_ID: str = env("KEELSON_INTERFACE_ID", "sh-1")

KEELSON_TAG: str = env("KEELSON_INTERFACE_TAG", "TODO")

LOG_LEVEL = env.log_level("LOG_LEVEL", logging.DEBUG)

# Setup logger
logger = logging.getLogger("keelson-docker-sdk")
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=LOG_LEVEL
)
logging.captureWarnings(True)
warnings.filterwarnings("once")


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

keyExp = brefv.construct_pub_sub_topic(
    realm=KEELSON_REALM,
    entity_id=KEELSON_ENTITY_ID,
    interface_type=KEELSON_INTERFACE_TYPE,
    interface_id=KEELSON_INTERFACE_ID,
    tag="docker",
    source_id="id",
)

logger.info("keyExp: %s", keyExp)

key = keyExp
# key = args.key
value = args.value
complete = args.complete


# Setting up ZENOH session
session = zenoh.open(conf)


def queryable_callback(query):
    logger.debug(f">> [Queryable ] Received Query '{query.selector}'")
    logger.debug(">> [Queryable ] Parameters", query.parameters, type(query.parameters))

    if query.parameters == "":
        logger.debug(">> [Queryable ] No parameters")
        list_of_containers = export_container_info()
        string_of_containers = json.dumps(list_of_containers)
        bytes_of_containers = string_of_containers.encode()

        # Publishing to zenoh
        try:
            payload = TimestampedBytes()
            payload.timestamp.FromNanoseconds(time.time_ns())
            payload.value = bytes_of_containers  # Should be bytes

            # no wrap ...
            message = brefv.enclose(bytes_of_containers)

            # message = brefv.enclose(payload.SerializeToString())
            # session.put(topic, message, **publisher_config)
            # query.reply(Sample(key, value))  # REAPLY TO QUERY

            logger.debug(">> [Queryable ] Publishing to topic", keyExp)
            logger.debug(">> [Queryable ] Publishing message", message)
            query.reply(Sample(keyExp, message))  # REAPLY TO QUERY

        except Exception:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to send to zenoh")

    else:
        query_args = query.parameters.split("&")
        logger.debug(">> [Queryable ] Parameters", query_args, type(query_args))
        for query_value in query_args:
            query_arg = query_value.split("=")
            logger.debug(">> [Queryable ] query_arg & Val", query_arg[0])

            if query_arg[0] == "logs":
                container_id = query_arg[1]
                logger.debug(">> [Queryable ] Value: container_id", container_id)
                container_log = get_container_logs(container_id)
                logger.debug(">> [Queryable ] Value: container_log", container_log)
                string_of_containers = json.dumps(container_log)
                bytes_of_containers = string_of_containers.encode()

                # Publishing to zenoh
                try:
                    payload = TimestampedBytes()
                    payload.timestamp.FromNanoseconds(time.time_ns())
                    payload.value = bytes_of_containers  # Should be bytes

                    # no wrap ...
                    message = brefv.enclose(bytes_of_containers)

                    # message = brefv.enclose(payload.SerializeToString())
                    # session.put(topic, message, **publisher_config)
                    # query.reply(Sample(key, value))  # REAPLY TO QUERY

                    logger.debug(">> [Queryable ] Publishing to topic", keyExp)
                    logger.debug(">> [Queryable ] Publishing message", message)
                    query.reply(Sample(keyExp, message))  # REAPLY TO QUERY

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to send to zenoh")

            elif query_arg[0] == "start":
                container_id = query_arg[1]
                logger.debug(">> [Queryable ] Start container_id:", container_id)
                status = start_container(container_id)
                logger.debug(">> [Queryable ] Start status:", status)
                string_of_status = json.dumps(
                    {"id": container_id, "status": status}
                )
                string_of_status = string_of_status.encode()

                # Publishing to zenoh
                try:
                    payload = TimestampedBytes()
                    payload.timestamp.FromNanoseconds(time.time_ns())
                    payload.value = string_of_status  # Should be bytes
                    message = brefv.enclose(string_of_status)
                    logger.debug(">> [Queryable ] Publishing to topic", keyExp)
                    logger.debug(">> [Queryable ] Publishing message", message)
                    query.reply(Sample(keyExp, message))  # REAPLY TO QUERY

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to send to zenoh")


            elif query_arg[0] == "stop":
                container_id = query_arg[1]
                logger.debug(">> [Queryable ] Stop container_id:", container_id)
                status = stop_container(container_id)
                logger.debug(">> [Queryable ] Stop status:", status)
                string_of_status = json.dumps(
                    {"id": container_id, "status": status}
                )
                string_of_status = string_of_status.encode()

                # Publishing to zenoh
                try:
                    payload = TimestampedBytes()
                    payload.timestamp.FromNanoseconds(time.time_ns())
                    payload.value = string_of_status  # Should be bytes
                    message = brefv.enclose(string_of_status)
                    logger.debug(">> [Queryable ] Publishing to topic", keyExp)
                    logger.debug(">> [Queryable ] Publishing message", message)
                    query.reply(Sample(keyExp, message))  # REAPLY TO QUERY

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to send to zenoh")

            elif query_arg[0] == "restart":
                container_id = query_arg[1]
                logger.debug(">> [Queryable ] Restart container_id:", container_id)
                status = restart_container(container_id)
                logger.debug(">> [Queryable ] Restart status:", status)
                string_of_status = json.dumps(
                    {"id": container_id, "status": status}
                )
                string_of_status = string_of_status.encode()

                # Publishing to zenoh
                try:
                    payload = TimestampedBytes()
                    payload.timestamp.FromNanoseconds(time.time_ns())
                    payload.value = string_of_status  # Should be bytes
                    message = brefv.enclose(string_of_status)
                    logger.debug(">> [Queryable ] Publishing to topic", keyExp)
                    logger.debug(">> [Queryable ] Publishing message", message)
                    query.reply(Sample(keyExp, message))  # REAPLY TO QUERY

                except Exception:  # pylint: disable=broad-exception-caught
                    logger.exception("Failed to send to zenoh")


            else:
                logger.error(">> [Queryable ] Unknown parameter", query_arg[0])


if __name__ == "__main__":
    try:
        logger.debug("Declaring Queryable on '{}'...".format(key))
        queryable = session.declare_queryable(key, queryable_callback, complete)

        while True:
            time.sleep(1)
            # forever loop

    finally:
        session.close()
