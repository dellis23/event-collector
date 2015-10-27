import datetime
import unittest

import sysv_ipc
import webtest

from events import collector, queue


class CollectorFunctionalTests(unittest.TestCase):
    def setUp(self):
        class MockDatetime(datetime.datetime):
            @classmethod
            def utcnow(cls):
                return datetime.datetime(2015, 11, 17, 12, 34, 56)
        datetime.datetime = MockDatetime

        app = collector.make_app(global_config={}, **{
            "key.TestKey1": "dGVzdA==",
            "msgq.events": "0xcafe",
            "msgq.errors": "0xdecaf",
            "allowed_origins": "example.com",
        })
        self.test_app = webtest.TestApp(app)
        self.events_queue = queue.SysVMessageQueue(key=0xcafe)
        self.errors_queue = queue.SysVMessageQueue(key=0xdecaf)

    def tearDown(self):
        self.events_queue.queue.remove()
        self.errors_queue.queue.remove()

    def test_batch(self):
        self.test_app.post("/v1",
            '[{"event1": "value"}, {"event2": "value"}]',
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TestApp/1.0",
                "Date": "Wed, 25 Nov 2015 06:25:24 GMT",
                "X-Signature": "key=TestKey1, mac=d7aab40b9db8ae0e0b40d98e9c50b2cfc80ca06127b42fbbbdf146752b47a5ed",
            },
            extra_environ={
                "REMOTE_ADDR": "1.2.3.4",
            },
        )

        event1, ignored = self.events_queue.queue.receive(block=False)
        self.assertEqual(event1, '{"ip": "1.2.3.4", "event": {"event1": "value"}, "time": "2015-11-17T12:34:56"}')
        event2, ignored = self.events_queue.queue.receive(block=False)
        self.assertEqual(event2, '{"ip": "1.2.3.4", "event": {"event2": "value"}, "time": "2015-11-17T12:34:56"}')

        with self.assertRaises(sysv_ipc.BusyError):
            self.errors_queue.queue.receive(block=False)

    def test_cors(self):
        response = self.test_app.options("/v1", headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Signature",
        })

        self.assertEqual(response.status_code, 204)
