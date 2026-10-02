import io
import json
import importlib
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from pavilion.unittest import PavTestCase


class RabbitMQLoggerTests(PavTestCase):
    def set_up(self):
        try:
            self.rabbitmq_logger = importlib.import_module(
                "pavilion.result_logging.rabbitmq_logger"
            )
        except (ImportError, SystemExit):
            self.skipTest("pika is required to import the RabbitMQ logger module.")

    def _connection_params(self):
        cert_file = Path(__file__).resolve().as_posix()

        return {
            "ca_cert_file": cert_file,
            "cert_file": cert_file,
            "key_file": cert_file,
            "host": "mq.example.com",
            "port": 5671,
            "vhost": "pavilion",
            "exchange": "pavilion.results",
            "routing_key": "test.result",
        }

    def _password_connection_params(self):
        return {
            "host": "mq.example.com",
            "port": 5672,
            "vhost": "pavilion",
            "exchange": "pavilion.results",
            "routing_key": "test.result",
            "username": "pav-user",
            "password": "pav-password",
        }

    def _make_params_file(self, params=None):
        if params is None:
            params = self._connection_params()

        with tempfile.NamedTemporaryFile("w", delete=False) as params_file:
            json.dump(params, params_file)
            return params_file.name, params

    def test_client_initializes_connection_and_sends_json(self):
        params = self._connection_params()
        context = mock.Mock()
        ssl_options = mock.sentinel.ssl_options
        credentials = mock.sentinel.credentials
        connection_params = mock.sentinel.connection_params
        properties = mock.sentinel.properties
        channel = mock.Mock()
        connection = mock.Mock()
        connection.channel.return_value = channel

        with ExitStack() as stack:
            create_context = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger.ssl,
                    "create_default_context",
                    return_value=context,
                )
            )
            ssl_options_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger, "SSLOptions", return_value=ssl_options
                )
            )
            credentials_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger,
                    "ExternalCredentials",
                    return_value=credentials,
                )
            )
            connection_params_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger,
                    "ConnectionParameters",
                    return_value=connection_params,
                )
            )
            connection_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger, "BlockingConnection", return_value=connection
                )
            )
            properties_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger, "BasicProperties", return_value=properties
                )
            )
            client = self.rabbitmq_logger.RabbitMQClient(params)

        create_context.assert_called_once_with(cafile=params["ca_cert_file"])
        context.load_cert_chain.assert_called_once_with(
            params["cert_file"], params["key_file"]
        )
        self.assertEqual(context.check_hostname, False)
        ssl_options_cls.assert_called_once_with(context, params["host"])
        credentials_cls.assert_called_once_with()
        connection_params_cls.assert_called_once_with(
            host=params["host"],
            port=params["port"],
            virtual_host=params["vhost"],
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=60,
        )
        connection_cls.assert_called_once_with(connection_params)
        properties_cls.assert_called_once_with(
            content_type="text/plain",
            delivery_mode=2,
        )

        results = {"hello": "world"}
        client.send_as_json(results)
        channel.basic_publish.assert_called_once_with(
            exchange=params["exchange"],
            routing_key=params["routing_key"],
            body=json.dumps(results),
            properties=properties,
        )

        client.process_data_events(1.9)
        connection.process_data_events.assert_called_once_with(time_limit=1)

    def test_client_initializes_password_connection(self):
        params = self._password_connection_params()
        credentials = mock.sentinel.credentials
        connection_params = mock.sentinel.connection_params
        connection = mock.Mock()

        with ExitStack() as stack:
            create_context = stack.enter_context(
                mock.patch.object(self.rabbitmq_logger.ssl, "create_default_context")
            )
            external_credentials_cls = stack.enter_context(
                mock.patch.object(self.rabbitmq_logger, "ExternalCredentials")
            )
            plain_credentials_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger,
                    "PlainCredentials",
                    return_value=credentials,
                )
            )
            connection_params_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger,
                    "ConnectionParameters",
                    return_value=connection_params,
                )
            )
            connection_cls = stack.enter_context(
                mock.patch.object(
                    self.rabbitmq_logger,
                    "BlockingConnection",
                    return_value=connection,
                )
            )

            self.rabbitmq_logger.RabbitMQClient(params)

        create_context.assert_not_called()
        external_credentials_cls.assert_not_called()
        plain_credentials_cls.assert_called_once_with("pav-user", "pav-password")
        connection_params_cls.assert_called_once_with(
            host=params["host"],
            port=params["port"],
            virtual_host=params["vhost"],
            credentials=credentials,
            heartbeat=60,
        )
        connection_cls.assert_called_once_with(connection_params)

    def test_client_verbose_negative_skips_publish(self):
        client = self.rabbitmq_logger.RabbitMQClient.__new__(
            self.rabbitmq_logger.RabbitMQClient
        )
        client.channel = mock.Mock()
        client.mqExchange = "exchange"
        client.mqRoutingKey = "route"
        client.properties = mock.sentinel.properties

        client.send_as_string("message", verbose=-1)

        client.channel.basic_publish.assert_not_called()

    def test_client_sends_plain_string_to_configured_route(self):
        client = self.rabbitmq_logger.RabbitMQClient.__new__(
            self.rabbitmq_logger.RabbitMQClient
        )
        client.channel = mock.Mock()
        client.mqExchange = "exchange"
        client.mqRoutingKey = "route"
        client.properties = mock.sentinel.properties

        client.send_as_string("plain message")

        client.channel.basic_publish.assert_called_once_with(
            exchange="exchange",
            routing_key="route",
            body="plain message",
            properties=mock.sentinel.properties,
        )

    def test_client_verbose_prints_and_still_publishes(self):
        client = self.rabbitmq_logger.RabbitMQClient.__new__(
            self.rabbitmq_logger.RabbitMQClient
        )
        client.channel = mock.Mock()
        client.mqExchange = "exchange"
        client.mqRoutingKey = "route"
        client.properties = mock.sentinel.properties

        with mock.patch("builtins.print") as print_mock:
            client.send_as_string("plain message", verbose=1)

        print_mock.assert_called_once_with("plain message")
        client.channel.basic_publish.assert_called_once_with(
            exchange="exchange",
            routing_key="route",
            body="plain message",
            properties=mock.sentinel.properties,
        )

    def test_client_context_manager_returns_client_and_closes_connection(self):
        client = self.rabbitmq_logger.RabbitMQClient.__new__(
            self.rabbitmq_logger.RabbitMQClient
        )
        client.connection = mock.Mock()

        with client as entered_client:
            self.assertIs(entered_client, client)

        client.connection.close.assert_called_once_with()

    def test_client_context_manager_suppresses_close_failure(self):
        client = self.rabbitmq_logger.RabbitMQClient.__new__(
            self.rabbitmq_logger.RabbitMQClient
        )
        client.connection = mock.Mock()
        client.connection.close.side_effect = RuntimeError("close failed")

        client.__exit__(None, None, None)

        client.connection.close.assert_called_once_with()

    def test_factory_validate_config_rejects_invalid_configs(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        missing_path = Path(tempfile.gettempdir()) / "missing-rabbitmq-params.json"

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError, "does not match logger plugin"
        ):
            factory.validate_config({"plugin": "not-rabbitmq"})

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "either 'params_file' or inline RabbitMQ connection parameters",
        ):
            factory.validate_config({"plugin": "rabbitmq"})

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError, "params_file not found"
        ):
            factory.validate_config(
                {
                    "plugin": "rabbitmq",
                    "params_file": missing_path.as_posix(),
                }
            )

    def test_factory_resolves_inline_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params = self._connection_params()
        config = {"plugin": "rabbitmq"}
        config.update(params)
        config["port"] = "5671"
        config["exchange"] = ""
        config["routing_key"] = ""

        factory.validate_config(config)

        expected = params.copy()
        expected["exchange"] = ""
        expected["routing_key"] = ""
        self.assertEqual(factory.get_connection_params(config), expected)

    def test_factory_resolves_inline_password_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params = self._password_connection_params()
        config = {"plugin": "rabbitmq"}
        config.update(params)

        factory.validate_config(config)

        self.assertEqual(factory.get_connection_params(config), params)

    def test_factory_resolves_json_password_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params_file, params = self._make_params_file(self._password_connection_params())

        try:
            config = {"plugin": "rabbitmq", "params_file": params_file}
            factory.validate_config(config)

            self.assertEqual(factory.get_connection_params(config), params)
        finally:
            Path(params_file).unlink()

    def test_factory_rejects_invalid_authentication_modes(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params = self._password_connection_params()

        for key in ("username", "password"):
            config = {"plugin": "rabbitmq"}
            config.update(params)
            del config[key]

            with self.assertRaisesRegex(
                self.rabbitmq_logger.ResultLoggerPluginError,
                "username and password",
            ):
                factory.validate_config(config)

        config = {"plugin": "rabbitmq"}
        config.update(self._connection_params())
        config.update(params)

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "one authentication method",
        ):
            factory.validate_config(config)

    def test_factory_resolves_json_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params_file, params = self._make_params_file()

        try:
            config = {
                "plugin": "rabbitmq",
                "params_file": params_file,
            }
            factory.validate_config(config)

            self.assertEqual(factory.get_connection_params(config), params)
        finally:
            Path(params_file).unlink()

    def test_factory_resolves_relative_json_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        params_file, params = self._make_params_file()

        try:
            config = {
                "plugin": "rabbitmq",
                "params_file": os.path.relpath(params_file),
            }
            factory.validate_config(config)

            self.assertEqual(factory.get_connection_params(config), params)
        finally:
            Path(params_file).unlink()

    def test_factory_rejects_mixed_connection_parameter_sources(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        config = {
            "plugin": "rabbitmq",
            "params_file": "",
            "host": "mq.example.com",
        }

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "either 'params_file' or inline RabbitMQ connection parameters",
        ):
            factory.validate_config(config)

    def test_factory_rejects_missing_inline_connection_parameter(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        config = {"plugin": "rabbitmq"}
        config.update(self._connection_params())
        del config["host"]

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "host",
        ):
            factory.validate_config(config)

    def test_factory_rejects_invalid_inline_connection_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()

        for port in ("not-a-port", "0", "65536"):
            config = {"plugin": "rabbitmq"}
            config.update(self._connection_params())
            config["port"] = port

            with self.assertRaisesRegex(
                self.rabbitmq_logger.ResultLoggerPluginError,
                "port",
            ):
                factory.validate_config(config)

        config = {"plugin": "rabbitmq"}
        config.update(self._connection_params())
        config["ca_cert_file"] = "relative-ca.pem"

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "ca_cert_file.*absolute",
        ):
            factory.validate_config(config)

        config = {"plugin": "rabbitmq"}
        config.update(self._connection_params())
        config["cert_file"] = Path(tempfile.gettempdir()).as_posix()

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "cert_file.*existing file",
        ):
            factory.validate_config(config)

    def test_factory_rejects_malformed_json_parameters(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()

        for params in ([], "text", 5671):
            params_file, _ = self._make_params_file(params)
            try:
                with self.assertRaisesRegex(
                    self.rabbitmq_logger.ResultLoggerPluginError,
                    "JSON object",
                ):
                    factory.validate_config(
                        {"plugin": "rabbitmq", "params_file": params_file}
                    )
            finally:
                Path(params_file).unlink()

    def test_factory_rejects_non_integral_json_port(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()

        for port in (True, 5671.5):
            params = self._connection_params()
            params["port"] = port
            params_file, _ = self._make_params_file(params)
            try:
                with self.assertRaisesRegex(
                    self.rabbitmq_logger.ResultLoggerPluginError,
                    "port must be an integer",
                ):
                    factory.validate_config(
                        {"plugin": "rabbitmq", "params_file": params_file}
                    )
            finally:
                Path(params_file).unlink()

    def test_factory_make_logger_creates_rabbitmq_logger(self):
        params = self._connection_params()
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        outfile = io.StringIO()
        config = {"plugin": "rabbitmq"}
        config.update(params)

        with mock.patch.object(
            self.rabbitmq_logger, "RabbitMQClient", autospec=True
        ) as client_cls:
            logger = factory.make_logger(
                config,
                "s1",
                outfile=outfile,
            )

        client_cls.assert_called_once_with(params)
        self.assertIsInstance(logger, self.rabbitmq_logger.RabbitMQLogger)
        self.assertIs(logger.client, client_cls.return_value)
        self.assertIs(logger.outfile, outfile)

    def test_logger_log_sends_results_and_writes_status(self):
        client = mock.Mock()
        outfile = io.StringIO()
        logger = self.rabbitmq_logger.RabbitMQLogger(client, outfile=outfile)
        results = {"test_name": "unit-test", "result": "PASS"}

        logger.log(results)

        client.send_as_json.assert_called_once_with(results)
        output = outfile.getvalue()
        self.assertIn("RabbitMQLogger: Logging", output)
        self.assertIn("'unit-test'", output)

    def test_logger_log_message_describes_rabbitmq_destination(self):
        logger = self.rabbitmq_logger.RabbitMQLogger(mock.Mock())

        message = logger.get_log_message({"test_name": "unit-test"})

        self.assertEqual(
            message,
            "RabbitMQLogger: Logging {'test_name': 'unit-test'} to RabbitMQ...",
        )

    def test_logger_internal_log_sends_results_and_records_debug_message(self):
        client = mock.Mock()
        logger = self.rabbitmq_logger.RabbitMQLogger(client)
        results = {"test_name": "unit-test", "result": "PASS"}

        with self.assertLogs("RabbitMQLogger", level="DEBUG") as logs:
            logger._log(results)

        client.send_as_json.assert_called_once_with(results)
        self.assertIn("DEBUG:RabbitMQLogger:Result sent to RabbitMQ", logs.output)

    def test_logger_log_warns_when_publish_fails(self):
        client = mock.Mock()
        client.send_as_json.side_effect = RuntimeError("publish failed")
        outfile = io.StringIO()
        logger = self.rabbitmq_logger.RabbitMQLogger(client, outfile=outfile)
        results = {"test_name": "unit-test"}

        with self.assertLogs("RabbitMQLogger", level="WARNING") as logs:
            logger.log(results)

        self.assertTrue(
            any(
                "Failed to publish result to RabbitMQ" in message
                for message in logs.output
            )
        )
        self.assertIn(
            "WARNING: RabbitMQ publish failed for result unit-test",
            outfile.getvalue(),
        )

    def test_logger_cleanup_closes_client(self):
        client = mock.MagicMock()
        logger = self.rabbitmq_logger.RabbitMQLogger(client)

        logger.__del__()

        client.__exit__.assert_called_once_with(None, None, None)

    def test_logger_cleanup_suppresses_client_close_failure(self):
        client = mock.MagicMock()
        client.__exit__.side_effect = RuntimeError("close failed")
        logger = self.rabbitmq_logger.RabbitMQLogger(client)

        logger.__del__()

        client.__exit__.assert_called_once_with(None, None, None)
