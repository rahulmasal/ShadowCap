"""
Health alerting module — sends notifications when health status changes to CRITICAL

Supports webhook (Slack/Discord/Teams) and email notifications.
"""

import json
import logging
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List

import requests

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    WARNING = "warning"
    CRITICAL = "critical"
    RECOVERY = "recovery"


class HealthAlerter:
    """Sends health alerts via configured channels"""

    def __init__(self):
        self.webhook_url = os.environ.get("HEALTH_ALERT_WEBHOOK_URL")
        self.alert_email = os.environ.get("HEALTH_ALERT_EMAIL")
        self.smtp_host = os.environ.get("SMTP_HOST")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USER")
        self.smtp_password = os.environ.get("SMTP_PASSWORD")
        self._last_alert_state: Dict[str, str] = {}  # check_name -> last_level

    def should_alert(self, check_name: str, current_status: str) -> bool:
        """Determine if an alert should be sent (avoid spamming on repeated failures)"""
        last = self._last_alert_state.get(check_name)

        # Always alert on state change
        if last != current_status:
            self._last_alert_state[check_name] = current_status
            return True

        # Don't re-alert on same state (except recovery)
        return current_status == "healthy" and last != "healthy"

    def send_alert(
        self,
        check_name: str,
        level: AlertLevel,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send an alert through all configured channels

        Args:
            check_name: Name of the health check that triggered
            level: Alert severity level
            message: Human-readable alert message
            details: Optional dict with additional context

        Returns:
            True if at least one channel succeeded
        """
        if not self.should_alert(check_name, level.value):
            return False

        success = False

        if self.webhook_url:
            success = self._send_webhook(check_name, level, message, details) or success

        if self.alert_email and self.smtp_host:
            success = self._send_email(check_name, level, message, details) or success

        if not success and level == AlertLevel.CRITICAL:
            logger.critical(
                "HEALTH ALERT [%s] %s: %s — no alert channel configured!",
                level.value.upper(),
                check_name,
                message,
            )

        return success

    def _send_webhook(
        self,
        check_name: str,
        level: AlertLevel,
        message: str,
        details: Optional[Dict[str, Any]],
    ) -> bool:
        """Send alert via webhook (Slack/Discord/Teams compatible)"""
        emoji = {"warning": "⚠️", "critical": "🔴", "recovery": "✅"}.get(level.value, "ℹ️")

        payload = {
            "text": f"{emoji} ShadowCap Health Alert: {check_name}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{level.value.upper()}* — `{check_name}`\n{message}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Time: {datetime.now(timezone.utc).isoformat()}",
                        }
                    ],
                },
            ],
        }

        if details:
            payload["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```{json.dumps(details, indent=2)}```",
                    },
                }
            )

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("Health alert sent via webhook: %s", check_name)
                return True
            else:
                logger.error("Webhook alert failed: HTTP %d", response.status_code)
                return False
        except requests.RequestException as e:
            logger.error("Webhook alert failed: %s", e)
            return False

    def _send_email(
        self,
        check_name: str,
        level: AlertLevel,
        message: str,
        details: Optional[Dict[str, Any]],
    ) -> bool:
        """Send alert via email (SMTP)"""
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[ShadowCap] {level.value.upper()} — {check_name}"
            msg["From"] = self.smtp_user
            msg["To"] = self.alert_email

            body = f"""
ShadowCap Health Alert

Level: {level.value.upper()}
Check: {check_name}
Time: {datetime.now(timezone.utc).isoformat()}

Message:
{message}

Details:
{json.dumps(details, indent=2) if details else 'N/A'}
"""
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, self.alert_email, msg.as_string())

            logger.info("Health alert sent via email: %s", check_name)
            return True
        except Exception as e:
            logger.error("Email alert failed: %s", e)
            return False


# Global alerter instance
health_alerter = HealthAlerter()
