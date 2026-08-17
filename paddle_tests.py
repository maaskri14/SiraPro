import hashlib
import hmac
import unittest

import paddle


class PaddleSignatureTests(unittest.TestCase):

    def make_signature(self, secret: str, ts: str, body: bytes) -> str:
        signed_payload = f"{ts}:".encode("utf-8") + body

        signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()

        return f"ts={ts};h={signature}"

    def test_valid_signature(self):
        secret = "test-secret"
        body = b'{"event_type":"transaction.completed"}'
        ts = "1700000000"

        header = self.make_signature(secret, ts, body)

        self.assertTrue(
            paddle.verify_paddle_signature(
                body,
                header,
                secret
            )
        )

    def test_invalid_signature(self):
        secret = "test-secret"
        body = b'{"event_type":"transaction.completed"}'

        header = "ts=1700000000;h=wrong"

        self.assertFalse(
            paddle.verify_paddle_signature(
                body,
                header,
                secret
            )
        )


if __name__ == "__main__":
    unittest.main()
