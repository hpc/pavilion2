# -*- coding: utf-8 -*-
"""
RabbitMQ result logger for Pavilion.

This module provides a persistent RabbitMQ client that sends each test result
as JSON to a broker.  It is registered as a built‑in result‑logger plugin so
users can enable it via the ``result_loggers`` section of ``pavilion.yaml``.
"""

# ---------------------------------------------------------------------------
# RabbitMQ client (renamed from the original ``rabbitMQ`` script).
# ---------------------------------------------------------------------------

import os
import sys
import json
import ssl
from pika import BlockingConnection, ConnectionParameters, SSLOptions, BasicProperties
from pika.credentials import ExternalCredentials
import logging


class RabbitMQClient:
    """Thin wrapper around ``pika`` that connects using TLS certificates.

    The constructor expects a *params_file* JSON configuration with the
    following keys (identical to the original script)::

        {
            "ca_cert_file": "/path/to/ca.pem",
            "cert_file":    "/path/to/client_cert.pem",
            "key_file":     "/path/to/client_key.key",
            "host": "mq.example.com",
            "port": 5671,
            "vhost": "pavilion",
            "exchange": "pavilion",
            "routing_key": "test.result"
        }
    """

    def __init__(self, params_file: str):
        """Open a persistent TLS‑secured connection using the JSON *params_file*.

        Any exception during connection bubbles up to the caller – the logger
        will catch it and emit a warning.
        """
        # Load the JSON parameters.
        with open(params_file, "r") as f:
            params = json.load(f)

        # Build an SSL context using the supplied certificate files.
        context = ssl.create_default_context(cafile=params["ca_cert_file"])
        context.load_cert_chain(params["cert_file"], params["key_file"])  # type: ignore[arg-type]
        context.check_hostname = False
        ssl_options = SSLOptions(context, params["host"])

        # Build pika connection parameters.
        credentials = ExternalCredentials()
        connection_params = ConnectionParameters(
            host=params["host"],
            port=params["port"],
            virtual_host=params["vhost"],
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=60,
        )

        # Establish a blocking connection and a channel.
        self.connection = BlockingConnection(connection_params)
        self.channel = self.connection.channel()

        # Store exchange / routing information for later use.
        self.mqExchange = params["exchange"]
        self.mqRoutingKey = params["routing_key"]

        # Message properties – make the message persistent.
        self.properties = BasicProperties(content_type="text/plain", delivery_mode=2)

    # ---------------------------------------------------------------------
    # Public API – the logger only needs ``send_as_json``.
    # ---------------------------------------------------------------------
    def send_as_string(self, message: str, verbose: int = 0) -> None:
        """Publish *message* (a plain string) to the configured exchange.

        ``verbose`` mirrors the original script – a negative value prints the
        message only and skips the publish.
        """
        if verbose != 0:
            print(message)
            if verbose < 0:
                print("\n  INFO: verbose < 0: Not sending to rabbitmq!\n")
                return
        self.channel.basic_publish(
            exchange=self.mqExchange,
            routing_key=self.mqRoutingKey,
            body=message,
            properties=self.properties,
        )

    def send_as_json(self, my_dict: dict, verbose: int = 0) -> None:
        """Serialize *my_dict* to JSON and delegate to ``send_as_string``."""
        self.send_as_string(json.dumps(my_dict), verbose)

    # ---------------------------------------------------------------------
    # Context‑manager helpers – used by the logger's ``__del__``.
    # ---------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.connection.close()
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # Compatibility shim from the original script (unused by the logger).
    # ---------------------------------------------------------------------
    def process_data_events(self, time_limit: float = 0.1) -> None:
        # ``pika`` expects an int, but accepting float is fine – cast to int.
        self.connection.process_data_events(time_limit=int(time_limit))


# ---------------------------------------------------------------------------
# Result‑logger plugin implementation.
# ---------------------------------------------------------------------------

import io
from pathlib import Path
from typing import Optional, TextIO

from .base_classes import ResultLoggerPlugin, ResultLogger
from pavilion.errors import ResultLoggerPluginError
from pavilion import output


class RabbitMQLoggerFactory(ResultLoggerPlugin):
    """Factory that creates a :class:`RabbitMQLogger` from config.

    The configuration must contain a ``params_file`` entry that points to an
    absolute JSON file describing the RabbitMQ connection (see the class doc‑
    string above for the required format).
    """

    def __init__(self) -> None:
        super().__init__(
            name="rabbitmq",
            description=(
                "Log test results to a RabbitMQ broker (persistent connection)."
            ),
            priority=self.PRIO_CORE,
        )

    # ---------------------------------------------------------------------
    # Configuration validation.
    # ---------------------------------------------------------------------
    def validate_config(self, config: dict) -> None:
        if config.get("plugin") != self.name:
            raise ResultLoggerPluginError(
                f"Name {config.get('plugin')} does not match logger plugin '{self.name}'."
            )
        params_file = config.get("params_file")
        if not params_file:
            raise ResultLoggerPluginError(
                "Missing required 'params_file' for RabbitMQ logger."
            )
        if not Path(params_file).is_absolute():
            raise ResultLoggerPluginError(
                f"'params_file' must be an absolute path: {params_file}"
            )
        if not Path(params_file).exists():
            raise ResultLoggerPluginError(f"params_file not found: {params_file}")

    # ---------------------------------------------------------------------
    # Create the actual logger instance.
    # ---------------------------------------------------------------------
    def _make_logger(
        self,
        config: dict,
        sid: str,
        outfile: Optional[TextIO] = None,
    ) -> "RabbitMQLogger":
        # One persistent client per logger (and therefore per series).
        client = RabbitMQClient(config["params_file"])
        return RabbitMQLogger(client, outfile)


class RabbitMQLogger(ResultLogger):
    """Result logger that forwards the result dictionary to RabbitMQ.

    It writes a short human‑readable line to ``self.outfile`` (mirroring the
    existing file‑loggers) and, on failure, also writes a warning line to that
    same ``outfile`` while emitting a ``logging.warning``.
    """

    def __init__(self, client: RabbitMQClient, outfile: Optional[TextIO] = None):
        self.client = client  # persistent connection for the series
        self.outfile = outfile or io.StringIO()
        self.logger = logging.getLogger(self.__class__.__name__)

    def log(self, results: dict) -> None:
        # Consistent one‑line status message.
        output.fprint(
            self.outfile,
            f"{type(self).__name__}: Logging {results} to RabbitMQ...",
        )
        try:
            self.client.send_as_json(results)
            self.logger.debug("Result sent to RabbitMQ")
        except Exception as exc:  # noqa: BLE001
            # Emit a warning to the logging system.
            self.logger.warning(
                "Failed to publish result to RabbitMQ: %s", exc, exc_info=True
            )
            # Also write a warning line to the outfile for user visibility.
            output.fprint(
                self.outfile,
                f"WARNING: RabbitMQ publish failed for result {results.get('test_name', '?')}",
            )

    def __del__(self):
        """Close the underlying RabbitMQ connection when the logger is GC'd."""
        try:
            self.client.__exit__(None, None, None)
        except Exception:
            # Silently ignore cleanup errors – they should not affect the series.
            pass
