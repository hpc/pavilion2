import io
import json
import importlib
import tempfile
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

    def _make_params_file(self):
        params = {
            "ca_cert_file": "/tmp/ca.pem",
            "cert_file": "/tmp/client.pem",
            "key_file": "/tmp/client.key",
            "host": "mq.example.com",
            "port": 5671,
            "vhost": "pavilion",
            "exchange": "pavilion.results",
            "routing_key": "test.result",
        }

        with tempfile.NamedTemporaryFile("w", delete=False) as params_file:
            json.dump(params, params_file)
            return params_file.name, params

    def test_client_initializes_connection_and_sends_json(self):
        params_file, params = self._make_params_file()
        context = mock.Mock()
        ssl_options = mock.sentinel.ssl_options
        credentials = mock.sentinel.credentials
        connection_params = mock.sentinel.connection_params
        properties = mock.sentinel.properties
        channel = mock.Mock()
        connection = mock.Mock()
        connection.channel.return_value = channel

        with (
            mock.patch.object(
                self.rabbitmq_logger.ssl, "create_default_context", return_value=context
            ) as create_context,
            mock.patch.object(
                self.rabbitmq_logger, "SSLOptions", return_value=ssl_options
            ) as ssl_options_cls,
            mock.patch.object(
                self.rabbitmq_logger, "ExternalCredentials", return_value=credentials
            ) as credentials_cls,
            mock.patch.object(
                self.rabbitmq_logger,
                "ConnectionParameters",
                return_value=connection_params,
            ) as connection_params_cls,
            mock.patch.object(
                self.rabbitmq_logger, "BlockingConnection", return_value=connection
            ) as connection_cls,
            mock.patch.object(
                self.rabbitmq_logger, "BasicProperties", return_value=properties
            ) as properties_cls,
        ):
            client = self.rabbitmq_logger.RabbitMQClient(params_file)

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

        Path(params_file).unlink()

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

    def test_factory_validate_config_rejects_invalid_configs(self):
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        missing_path = Path(tempfile.gettempdir()) / "missing-rabbitmq-params.json"

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError, "does not match logger plugin"
        ):
            factory.validate_config({"plugin": "not-rabbitmq"})

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError,
            "Missing required 'params_file'",
        ):
            factory.validate_config({"plugin": "rabbitmq"})

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError, "must be an absolute path"
        ):
            factory.validate_config(
                {
                    "plugin": "rabbitmq",
                    "params_file": "rabbitmq-params.json",
                }
            )

        with self.assertRaisesRegex(
            self.rabbitmq_logger.ResultLoggerPluginError, "params_file not found"
        ):
            factory.validate_config(
                {
                    "plugin": "rabbitmq",
                    "params_file": missing_path.as_posix(),
                }
            )

    def test_factory_make_logger_creates_rabbitmq_logger(self):
        params_file, _ = self._make_params_file()
        factory = self.rabbitmq_logger.RabbitMQLoggerFactory()
        outfile = io.StringIO()

        with mock.patch.object(
            self.rabbitmq_logger, "RabbitMQClient", autospec=True
        ) as client_cls:
            logger = factory.make_logger(
                {
                    "plugin": "rabbitmq",
                    "params_file": params_file,
                },
                "s1",
                outfile=outfile,
            )

        client_cls.assert_called_once_with(params_file)
        self.assertIsInstance(logger, self.rabbitmq_logger.RabbitMQLogger)
        self.assertIs(logger.client, client_cls.return_value)
        self.assertIs(logger.outfile, outfile)

        Path(params_file).unlink()

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
