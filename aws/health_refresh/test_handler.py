"""Offline contract tests; only the AWS SDK and database driver are mocked."""
import importlib
import importlib.util
import json
import os
import ssl
import sys
import unittest
from unittest.mock import MagicMock, patch, call


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.aws = MagicMock()
        self.driver = MagicMock()
        self.modules = patch.dict(sys.modules, {
            "boto3": self.aws, "pg8000": self.driver,
            "pg8000.dbapi": self.driver.dbapi,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.env = patch.dict(os.environ, {"DB_SECRET_ARN": "secret-arn"}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.assertIsNotNone(importlib.util.find_spec("handler"), "handler not implemented")
        sys.modules.pop("handler", None)
        self.handler = importlib.import_module("handler")
        self.addCleanup(lambda: sys.modules.pop("handler", None))
        self.secret = dict(host="db.example", port=5432, dbname="dashboard",
                           user="refresh", password="sensitive-password")
        self.aws.client.return_value.get_secret_value.return_value = {
            "SecretString": json.dumps(self.secret)}
        self.conn = self.driver.dbapi.connect.return_value
        self.cursor = self.conn.cursor.return_value
        self.cursor.fetchone.return_value = (True,)

    def assert_sanitized_failure(self):
        with self.assertLogs(self.handler.__name__, level="INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "^Health refresh failed$") as caught:
                self.handler.lambda_handler({}, None)
        self.assertIsNone(caught.exception.__context__)
        self.assertEqual(len(logs.records), 1)
        self.assertRegex(logs.records[0].getMessage(), r"^status=error duration_ms=\d+$")
        self.assertIsNone(logs.records[0].exc_info)

    def test_connection_failure_does_not_attempt_cleanup_of_missing_connection(self):
        self.driver.dbapi.connect.side_effect = RuntimeError("sensitive-connect")
        self.assert_sanitized_failure()
        self.conn.close.assert_not_called()
        self.conn.rollback.assert_not_called()

    def test_secret_failure_does_not_open_connection(self):
        self.aws.client.return_value.get_secret_value.side_effect = RuntimeError("sensitive-secret")
        self.assert_sanitized_failure()
        self.driver.dbapi.connect.assert_not_called()

    def test_cursor_creation_failure_rolls_back_and_closes_connection(self):
        self.conn.cursor.side_effect = RuntimeError("sensitive-cursor-creation")
        self.assert_sanitized_failure()
        self.conn.rollback.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_commit_failure_rolls_back_and_closes(self):
        self.conn.commit.side_effect = RuntimeError("sensitive-commit")
        self.assert_sanitized_failure()
        self.conn.rollback.assert_called_once_with()
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_close_failure_after_commit_is_sanitized(self):
        self.cursor.close.side_effect = RuntimeError("sensitive-close")
        self.assert_sanitized_failure()
        self.conn.commit.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_success_logging_contains_only_status_and_duration(self):
        with self.assertLogs(self.handler.__name__, level="INFO") as logs:
            self.handler.lambda_handler({"patient": "sensitive-event"}, None)
        self.assertEqual(len(logs.records), 1)
        self.assertRegex(logs.records[0].getMessage(), r"^status=refreshed duration_ms=\d+$")
        self.assertIsNone(logs.records[0].exc_info)

    def test_unknown_tls_mode_fails_closed(self):
        os.environ["DB_TLS_MODE"] = "disable"
        with self.assertLogs(self.handler.__name__, level="INFO"):
            with self.assertRaisesRegex(RuntimeError, "^Health refresh failed$"):
                self.handler.lambda_handler({}, None)
        self.driver.dbapi.connect.assert_not_called()

    def test_require_mode_encrypts_without_certificate_verification(self):
        os.environ["DB_TLS_MODE"] = "require"
        self.handler.lambda_handler({}, None)
        tls = self.driver.dbapi.connect.call_args.kwargs["ssl_context"]
        self.assertIsInstance(tls, ssl.SSLContext)
        self.assertFalse(tls.check_hostname)
        self.assertEqual(tls.verify_mode, ssl.CERT_NONE)

    def test_cleanup_errors_are_sanitized_and_connection_still_closed(self):
        self.cursor.execute.side_effect = RuntimeError("sensitive-query")
        self.conn.rollback.side_effect = RuntimeError("sensitive-rollback")
        self.cursor.close.side_effect = RuntimeError("sensitive-cursor")
        self.conn.close.side_effect = RuntimeError("sensitive-close")
        with self.assertLogs(self.handler.__name__, level="INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "^Health refresh failed$"):
                self.handler.lambda_handler({}, None)
        self.conn.rollback.assert_called_once_with()
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()
        self.assertRegex(logs.records[0].getMessage(), r"^status=error duration_ms=\d+$")

    def test_database_error_is_sanitized_rolled_back_and_closed(self):
        self.cursor.execute.side_effect = [None, None, RuntimeError("sensitive-patient-content")]
        with self.assertLogs(self.handler.__name__, level="INFO") as logs:
            with self.assertRaisesRegex(RuntimeError, "^Health refresh failed$") as caught:
                self.handler.lambda_handler({}, None)
        import traceback
        rendered = "".join(traceback.format_exception(
            type(caught.exception), caught.exception, caught.exception.__traceback__))
        self.assertNotIn("sensitive-patient-content", rendered)
        self.assertEqual(len(logs.records), 1)
        self.assertRegex(logs.records[0].getMessage(), r"^status=error duration_ms=\d+$")
        self.assertIsNone(logs.records[0].exc_info)
        self.conn.rollback.assert_called_once_with()
        self.conn.commit.assert_not_called()
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()

    def test_lock_conflict_skips_call_and_releases_transaction(self):
        self.cursor.fetchone.return_value = (False,)
        self.assertEqual(self.handler.lambda_handler({}, None), {"status": "skipped"})
        self.assertNotIn(call("CALL public.refresh_health_dashboard()"),
                         self.cursor.execute.call_args_list)
        self.conn.commit.assert_called_once_with()
        self.conn.close.assert_called_once_with()
        self.cursor.close.assert_called_once_with()

    def test_success_uses_verified_tls_fixed_sql_and_commits(self):
        result = self.handler.lambda_handler({}, None)
        self.assertEqual(result, {"status": "refreshed"})
        self.aws.client.assert_called_once_with("secretsmanager")
        self.aws.client.return_value.get_secret_value.assert_called_once_with(SecretId="secret-arn")
        kwargs = self.driver.dbapi.connect.call_args.kwargs
        self.assertEqual({k: v for k, v in kwargs.items() if k != "ssl_context"},
                         dict(host="db.example", port=5432, database="dashboard",
                              user="refresh", password="sensitive-password"))
        self.assertIsInstance(kwargs["ssl_context"], ssl.SSLContext)
        self.assertEqual(kwargs["ssl_context"].verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(kwargs["ssl_context"].check_hostname)
        self.assertFalse(self.conn.autocommit)
        self.assertEqual(self.cursor.execute.call_args_list, [
            call("SET LOCAL statement_timeout='780s'"),
            call("SELECT pg_try_advisory_xact_lock(%s)", (724190381,)),
            call("CALL public.refresh_health_dashboard()"),
        ])
        self.conn.commit.assert_called_once_with()
        self.conn.rollback.assert_not_called()
        self.cursor.close.assert_called_once_with()
        self.conn.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
