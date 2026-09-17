"""Health dashboard refresh. Deploy with Lambda Timeout=840 seconds.

Dependencies: boto3 and pg8000. Entry point: handler.lambda_handler.
"""
import json
import logging
import os
import ssl
import time

import boto3
import pg8000.dbapi


ADVISORY_LOCK_ID = 724190381
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    started = time.monotonic()
    conn = None
    cursor = None
    status = "error"
    try:
        secret = json.loads(boto3.client("secretsmanager").get_secret_value(
            SecretId=os.environ["DB_SECRET_ARN"])["SecretString"])
        tls_mode = os.environ.get("DB_TLS_MODE", "verify-full")
        if tls_mode not in ("verify-full", "require"):
            raise ValueError("Invalid TLS mode")
        tls = ssl.create_default_context()
        if tls_mode == "require":
            # Explicit self-signed-server opt-in: encryption only, NOT authenticated.
            # CERT_NONE disables certificate validation and allows MITM attacks.
            tls.check_hostname = False
            tls.verify_mode = ssl.CERT_NONE
        conn = pg8000.dbapi.connect(
            host=secret["host"], port=int(secret["port"]), database=secret["dbname"],
            user=secret["user"], password=secret["password"],
            ssl_context=tls)
        conn.autocommit = False
        cursor = conn.cursor()
        cursor.execute("SET LOCAL statement_timeout='780s'")
        cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", (ADVISORY_LOCK_ID,))
        acquired = cursor.fetchone()[0]
        if acquired:
            cursor.execute("CALL public.refresh_health_dashboard()")
        conn.commit()
        status = "refreshed" if acquired else "skipped"
    except Exception:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass  # Cleanup failures must never expose driver error content.
    finally:
        for resource in (cursor, conn):
            if resource is not None:
                try:
                    resource.close()
                except Exception:
                    status = "error"
        logger.info("status=%s duration_ms=%d", status,
                    int((time.monotonic() - started) * 1000))
    if status == "error":
        # Outside the except block: no sensitive exception chain reaches Lambda logs.
        raise RuntimeError("Health refresh failed") from None
    return {"status": status}
