# -*- coding: utf-8 -*-
"""
RabbitMQ result logger for Pavilion.

This module provides a persistent RabbitMQ client that sends each test result
as JSON to a broker.  It is registered as a built‑in result‑logger plugin so
users can enable it via the ``result_loggers`` section of ``pavilion.yaml``.
"""

import json
import ssl
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


from pika import (
    BlockingConnection,
    ConnectionParameters,
    SSLOptions,
    BasicProperties,
)
from pika.credentials import ExternalCredentials
import logging

from .base_classes import ResultLoggerPlugin, ResultLogger
from pavilion.errors import ResultLoggerPluginError
from pavilion import output


RABBITMQ_PARAM_KEYS = (
    "ca_cert_file",
    "cert_file",
    "key_file",
    "host",
    "port",
    "vhost",
    "exchange",
    "routing_key",
)
CERT_FILE_KEYS = ("ca_cert_file", "cert_file", "key_file")
REQUIRED_PARAM_KEYS = (
    "ca_cert_file",
    "cert_file",
    "key_file",
    "host",
    "port",
    "vhost",
)


class RabbitMQClient:
    """Thin wrapper around ``pika`` that connects using TLS certificates.

    The constructor expects a parameter dictionary with the following keys::

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

    def __init__(self, params: Dict[str, Any]):
        """Open a persistent TLS-secured connection using ``params``.

        Any exception during connection bubbles up to the caller – the logger
        will catch it and emit a warning.
        """
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


class RabbitMQLoggerFactory(ResultLoggerPlugin):
    """Factory that creates a :class:`RabbitMQLogger` from config.

    Configuration accepts either an absolute ``params_file`` containing JSON
    parameters or all RabbitMQ parameters directly as top-level entries.
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
    def get_connection_params(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve and validate RabbitMQ connection parameters.

        :param config: result logger configuration
        :type config: dict
        :return: normalized connection parameters
        :rtype: dict
        """
        has_params_file = "params_file" in config
        params_file = config.get("params_file")
        inline_keys = [key for key in RABBITMQ_PARAM_KEYS if key in config]

        if has_params_file and inline_keys:
            raise ResultLoggerPluginError(
                "Specify either 'params_file' or inline RabbitMQ connection "
                "parameters, not both."
            )

        if has_params_file:
            if not params_file:
                raise ResultLoggerPluginError("'params_file' must not be empty.")
            params_path = Path(params_file)
            if not params_path.exists():
                raise ResultLoggerPluginError(
                    "params_file not found: {}".format(params_file)
                )
            try:
                with params_path.open() as params_file_obj:
                    params = json.load(params_file_obj)
            except (OSError, ValueError) as err:
                raise ResultLoggerPluginError(
                    "Could not load RabbitMQ params_file '{}': {}".format(
                        params_path, err
                    )
                )
        elif inline_keys:
            params = {key: config.get(key) for key in RABBITMQ_PARAM_KEYS}
        else:
            raise ResultLoggerPluginError(
                "Specify either 'params_file' or inline RabbitMQ connection parameters."
            )

        if not isinstance(params, dict):
            raise ResultLoggerPluginError(
                "RabbitMQ params_file must contain a JSON object."
            )

        missing = [key for key in REQUIRED_PARAM_KEYS if not params.get(key)]
        if missing:
            raise ResultLoggerPluginError(
                "Missing required RabbitMQ parameter(s): {}.".format(", ".join(missing))
            )

        normalized = {key: params[key] for key in RABBITMQ_PARAM_KEYS}
        for key in CERT_FILE_KEYS:
            cert_path_value = normalized[key]
            if not isinstance(cert_path_value, str):
                raise ResultLoggerPluginError(
                    "'{}' must be an absolute path to an existing file.".format(key)
                )
            cert_path = Path(cert_path_value)
            if not cert_path.is_absolute():
                raise ResultLoggerPluginError(
                    "'{}' must be an absolute path: {}".format(key, cert_path)
                )
            if not cert_path.is_file():
                raise ResultLoggerPluginError(
                    "'{}' must be an existing file: {}".format(key, cert_path)
                )

        port = normalized["port"]
        if isinstance(port, bool):
            raise ResultLoggerPluginError(
                "RabbitMQ port must be an integer: {}".format(port)
            )
        if isinstance(port, int):
            normalized["port"] = int(port)
        elif isinstance(port, str):
            try:
                normalized["port"] = int(port)
            except ValueError:
                raise ResultLoggerPluginError(
                    "RabbitMQ port must be an integer: {}".format(port)
                )
        else:
            raise ResultLoggerPluginError(
                "RabbitMQ port must be an integer: {}".format(port)
            )
        if not 1 <= normalized["port"] <= 65535:
            raise ResultLoggerPluginError(
                "RabbitMQ port must be between 1 and 65535: {}".format(
                    normalized["port"]
                )
            )

        return normalized

    def validate_config(self, config: Dict[str, Any]) -> None:
        if config.get("plugin") != self.name:
            raise ResultLoggerPluginError(
                f"Name {config.get('plugin')} does not match logger plugin '{self.name}'."
            )

        self.get_connection_params(config)

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
        # TODO: This opens the rabbitmq connection. Where should the connection actually be opened so that
        # - is efficient if lots of results are sent
        # - it works for long-running Pavilion runs (e.g. 1-2 days long (viz. continuous testing))
        client = RabbitMQClient(self.get_connection_params(config))
        return RabbitMQLogger(client, outfile)


class RabbitMQLogger(ResultLogger):
    """Result logger that forwards the result dictionary to RabbitMQ.

    It writes a short human‑readable line to ``self.outfile`` (mirroring the
    existing file‑loggers) and, on failure, also writes a warning line to that
    same ``outfile`` while emitting a ``logging.warning``.
    """

    def __init__(self, client: RabbitMQClient, outfile: Optional[TextIO] = None):
        super().__init__(name=type(self).__name__, outfile=outfile)
        self.client = client  # persistent connection for the series
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_log_message(self, results: dict) -> str:
        return f"{type(self).__name__}: Logging {results} to RabbitMQ..."

    def _log(self, results: dict) -> None:
        self.client.send_as_json(results)
        self.logger.debug("Result sent to RabbitMQ")

    def log(self, results: dict) -> None:
        # Consistent one‑line status message.
        output.fprint(
            self.outfile,
            self.get_log_message(results),
        )
        try:
            self._log(results)
        ## TODO: what exceptions to catch here?
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
