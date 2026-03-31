#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression guards for extracted mini-program auth service logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from application.services import miniprogram_auth as svc


class _LoggerStub:
    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None


class MiniprogramServiceExtractionTests(unittest.TestCase):
    def setUp(self):
        self.logger = _LoggerStub()

    def test_format_datetime_for_frontend_handles_datetime_and_none(self):
        self.assertIsNone(svc.format_datetime_for_frontend(None))
        dt = datetime(2026, 1, 1, 10, 20, 30)
        self.assertEqual(svc.format_datetime_for_frontend(dt), "2026-01-01T10:20:30")

    def test_login_returns_not_activated_success_payload(self):
        user = {"id": 1, "is_activated": 0, "expires_at": None, "nickname": "u", "avatar_url": None}
        with (
            patch.object(svc, "get_openid_from_wechat", return_value={"openid": "oid_1", "unionid": None}),
            patch.object(svc, "get_user_by_openid", return_value=user),
        ):
            result = svc.login_with_wechat_code("code", self.logger)
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["status"], "NOT_ACTIVATED")
        self.assertFalse(result["data"]["is_activated"])

    def test_login_returns_expired_error_when_expires_at_in_past(self):
        user = {
            "id": 1,
            "is_activated": 1,
            "expires_at": datetime.utcnow() - timedelta(days=1),
            "nickname": "u",
            "avatar_url": None,
            "unionid": None,
        }
        with (
            patch.object(svc, "get_openid_from_wechat", return_value={"openid": "oid_1", "unionid": None}),
            patch.object(svc, "get_user_by_openid", return_value=user),
            patch.object(svc, "to_timezone_aware", side_effect=lambda x: x.replace(tzinfo=timezone.utc)),
        ):
            result = svc.login_with_wechat_code("code", self.logger)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["error_code"], "EXPIRED_TOKEN")

    def test_activate_rejects_already_activated(self):
        user = {"id": 7, "is_activated": 1, "expires_at": datetime.utcnow()}
        with (
            patch.object(svc, "get_openid_from_wechat", return_value={"openid": "oid_1", "unionid": None}),
            patch.object(svc, "get_user_by_openid", return_value=user),
        ):
            result = svc.activate_with_wechat_code("code", "INVITE", self.logger)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], 400)
        self.assertEqual(result["error_code"], "ALREADY_ACTIVATED")


if __name__ == "__main__":
    unittest.main()
