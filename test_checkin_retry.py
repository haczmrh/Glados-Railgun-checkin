import unittest
from unittest.mock import Mock, call, patch

import requests

from checkin import API, CheckinStatus


def response(status, payload=None):
    result = requests.Response()
    result.status_code = status
    result.close = Mock()
    result.json = Mock(return_value=payload)
    return result


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.api = API("glados.cloud")
        self.api.session = Mock()
        self.addCleanup(self.api.close)
        self.sleep = patch("checkin.time.sleep").start()
        self.addCleanup(patch.stopall)

    def test_checkin_recovers_from_gateway_error(self):
        failed = response(502)
        self.api.session.post.side_effect = [
            failed, response(200, {"code": 0, "points": 1, "message": "ok"})
        ]
        result = self.api.checkin("private-cookie")
        self.assertEqual(result["code"], CheckinStatus.SUCCESS)
        self.assertEqual(self.api.session.post.call_count, 2)
        self.sleep.assert_called_once_with(15)
        failed.close.assert_called_once()

    def test_checkin_repeat_after_timeout_is_successful_outcome(self):
        self.api.session.post.side_effect = [
            requests.exceptions.ReadTimeout(),
            response(200, {"code": 1, "message": "already checked in"}),
        ]
        self.assertEqual(self.api.checkin("private-cookie")["code"], CheckinStatus.REPEAT)
        self.assertEqual(self.api.session.post.call_count, 2)

    def test_persistent_gateway_error_is_bounded_and_fails(self):
        self.api.session.post.side_effect = [response(502) for _ in range(4)]
        self.assertEqual(self.api.checkin("private-cookie")["code"], CheckinStatus.FAILURE)
        self.assertEqual(self.api.session.post.call_count, 4)
        self.assertEqual(self.sleep.call_args_list, [call(15), call(30), call(60)])

    def test_authentication_failure_is_not_retried(self):
        for status in (401, 403):
            with self.subTest(status=status):
                self.api.session.post.reset_mock()
                self.api.session.post.return_value = response(status)
                self.assertEqual(self.api.checkin("private-cookie")["code"], CheckinStatus.FAILURE)
                self.api.session.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_json_authentication_failure_is_not_retried(self):
        self.api.session.post.return_value = response(200, {"code": -1, "message": "expired"})
        self.assertEqual(self.api.checkin("private-cookie")["code"], CheckinStatus.FAILURE)
        self.api.session.post.assert_called_once()
        self.sleep.assert_not_called()

    def test_status_query_recovers_from_connection_error(self):
        self.api.session.get.side_effect = [
            requests.exceptions.ConnectionError(),
            response(200, {"code": 0, "data": {"leftDays": "20.5"}}),
        ]
        self.assertEqual(self.api.get_status("private-cookie"), ("20 天", 0))
        self.assertEqual(self.api.session.get.call_count, 2)

    def test_exchange_is_never_retried(self):
        for failure in (response(502), requests.exceptions.ReadTimeout()):
            with self.subTest(failure=type(failure).__name__):
                self.api.session.post.reset_mock()
                self.api.session.post.side_effect = [failure]
                self.assertEqual(self.api.exchange("private-cookie", "plan500", 500), "兑换失败")
                self.api.session.post.assert_called_once()
        self.sleep.assert_not_called()


if __name__ == "__main__":
    unittest.main()
