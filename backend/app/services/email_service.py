"""
Email service — sends transactional emails via SendGrid.
Path: backend/app/services/email_service.py
"""
import logging
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """
    Send a password reset email via SendGrid.
    Returns True if sent successfully, False if skipped (no API key) or failed.
    """
    if not settings.SENDGRID_API_KEY:
        logger.warning(
            "SENDGRID_API_KEY not configured — password reset email not sent to %s. "
            "In dev mode, use the reset_url returned by the API.",
            to_email,
        )
        return False

    subject = "Reset your TradeAI password"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background-color:#f4f4f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
        <table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;padding:40px 0;">
            <tr>
                <td align="center">
                    <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;">
                        <tr>
                            <td style="background:linear-gradient(135deg,#3b82f6,#8b5cf6);padding:32px 40px;text-align:center;">
                                <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:700;">TradeAI</h1>
                                <p style="color:rgba(255,255,255,0.85);margin:8px 0 0;font-size:14px;">Password Reset Request</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:32px 40px;">
                                <p style="color:#374151;font-size:15px;line-height:1.6;margin:0 0 20px;">
                                    We received a request to reset your TradeAI account password.
                                    Click the button below to set a new password.
                                </p>
                                <table role="presentation" width="100%%" cellpadding="0" cellspacing="0">
                                    <tr>
                                        <td align="center" style="padding:8px 0 24px;">
                                            <a href="{reset_url}"
                                               style="background-color:#3b82f6;color:#ffffff;padding:12px 32px;border-radius:8px;
                                                      text-decoration:none;font-weight:600;font-size:14px;display:inline-block;">
                                                Reset Password
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                <p style="color:#6b7280;font-size:13px;line-height:1.5;margin:0 0 12px;">
                                    Or copy and paste this link into your browser:
                                </p>
                                <p style="color:#3b82f6;font-size:12px;word-break:break-all;margin:0;">
                                    <a href="{reset_url}" style="color:#3b82f6;">{reset_url}</a>
                                </p>
                                <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;" />
                                <p style="color:#9ca3af;font-size:12px;line-height:1.5;margin:0;">
                                    This link will expire in 1 hour. If you did not request a password reset,
                                    you can safely ignore this email.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    message = Mail(
        from_email=Email(settings.FROM_EMAIL, "TradeAI"),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html_content),
    )

    try:
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(
            "Password reset email sent to %s (status=%s)",
            to_email,
            response.status_code,
        )
        return True
    except Exception as e:
        logger.error("Failed to send password reset email to %s: %s", to_email, e)
        return False
