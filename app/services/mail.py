from pydantic import BaseModel, EmailStr
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv
import os
from enum import Enum
import resend
import inspect

# Load environment variables
load_dotenv()

# Initialize resend with API key
resend.api_key = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")

# Email Types Enum
class EmailType(str, Enum):
    ACCOUNT_VERIFICATION = "account_verification"
    PASSWORD_RESET = "password_reset"
    STAFF_ACCOUNT_CREATED = "staff_account_created"
    APPLICATION_SUBMITTED = "application_submitted"
    APPLICATION_STATUS_UPDATE = "application_status_update"
    OTP_VERIFICATION = "otp_verification"

# Email Schema
class EmailSchema(BaseModel):
    email: List[EmailStr]
    subject: str
    body: str

# ─── Base Template ────────────────────────────────────────────────────────────

def get_base_template(content: str) -> str:
    """Base HTML template with BNR branding and #753918 color scheme"""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f4f5;
            color: #18181b;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .wrapper {{
            width: 100%;
            background-color: #f4f4f5;
            padding: 40px 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background-color: #753918;
            padding: 32px;
            text-align: center;
        }}
        .header-text {{
            color: #ffffff;
            margin: 0;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        .content {{
            padding: 40px;
            line-height: 1.7;
        }}
        .footer {{
            padding: 32px;
            text-align: center;
            font-size: 13px;
            color: #71717a;
            background-color: #fafafa;
            border-top: 1px solid #f4f4f5;
        }}
        .btn {{
            display: inline-block;
            background-color: #753918;
            color: #ffffff !important;
            padding: 14px 28px;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 24px 0;
            text-align: center;
        }}
        .highlight {{
            color: #753918;
            font-weight: 600;
        }}
        .info-box {{
            background-color: #fdfaf9;
            border-left: 4px solid #753918;
            padding: 20px;
            margin: 24px 0;
            border-radius: 0 8px 8px 0;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="container">
            <div class="header">
                <div class="header-text">BNR Licensing Portal</div>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                &copy; {os.getenv("CURRENT_YEAR", "2024")} National Bank of Rwanda (BNR).<br>
                All rights reserved. Regulatory and Compliance Division.
            </div>
        </div>
    </div>
</body>
</html>
"""

# ─── Email Templates ──────────────────────────────────────────────────────────

def get_account_verification_template(user_fullname: str, verification_link: str) -> str:
    content = f"""
        <h2 style="margin-top: 0;">Confirm your email address</h2>
        <p>Hello {user_fullname},</p>
        <p>Thank you for registering on the BNR Licensing Portal. To complete your account setup and start your application, please verify your email address by clicking the button below:</p>
        <div style="text-align: center;">
            <a href="{verification_link}" class="btn">Verify Email Address</a>
        </div>
        <p>If the button doesn't work, copy and paste this link into your browser:</p>
        <p style="word-break: break-all; font-size: 13px; color: #71717a;">{verification_link}</p>
        <p>This link will expire in 24 hours.</p>
    """
    return get_base_template(content)

def get_otp_verification_template(user_fullname: str, otp: str) -> str:
    content = f"""
        <h2 style="margin-top: 0;">Your Verification Code</h2>
        <p>Hello {user_fullname},</p>
        <p>Your OTP verification code for the BNR Licensing Portal is:</p>
        <div style="text-align: center; margin: 30px 0;">
            <div style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #753918; padding: 15px; border: 2px dashed #753918; display: inline-block; border-radius: 8px;">
                {otp}
            </div>
        </div>
        <p>This code will expire in 15 minutes.</p>
        <p>If you did not request this code, please ignore this email.</p>
    """
    return get_base_template(content)

def get_password_reset_template(user_fullname: str, reset_link: str) -> str:
    content = f"""
        <h2 style="margin-top: 0;">Reset your password</h2>
        <p>Hello {user_fullname},</p>
        <p>We received a request to reset the password for your account on the BNR Licensing Portal. Click the button below to set a new password:</p>
        <div style="text-align: center;">
            <a href="{reset_link}" class="btn">Reset Password</a>
        </div>
        <p>If you didn't request a password reset, you can safely ignore this email.</p>
        <p>For security, this link will expire in 1 hour.</p>
    """
    return get_base_template(content)

def get_staff_account_created_template(user_fullname: str, temporary_password: str, login_link: str, role: str) -> str:
    content = f"""
        <h2 style="margin-top: 0;">Staff Account Created</h2>
        <p>Hello {user_fullname},</p>
        <p>An administrative account has been created for you on the BNR Licensing Portal with the role of <span class="highlight">{role}</span>.</p>
        <div class="info-box">
            <strong>Temporary Credentials:</strong><br>
            Password: <code style="background: #f1f1f1; padding: 2px 6px; border-radius: 4px;">{temporary_password}</code>
        </div>
        <p>For security reasons, you will be required to change this password upon your first login.</p>
        <div style="text-align: center;">
            <a href="{login_link}" class="btn">Login to Portal</a>
        </div>
    """
    return get_base_template(content)

def get_application_status_update_template(user_fullname: str, application_id: str, status: str, notes: Optional[str] = None) -> str:
    status_colors = {
        "APPROVED": "#16a34a",
        "REJECTED": "#dc2626",
        "INFORMATION_REQUESTED": "#ca8a04",
        "UNDER_REVIEW": "#753918"
    }
    color = status_colors.get(status, "#753918")

    content = f"""
        <h2 style="margin-top: 0;">Application Status Update</h2>
        <p>Hello {user_fullname},</p>
        <p>The status of your application <span class="highlight">#{application_id}</span> has been updated to:</p>
        <div style="display: inline-block; padding: 8px 16px; background-color: {color}; color: #ffffff; border-radius: 6px; font-weight: 700; margin: 10px 0;">
            {status.replace('_', ' ')}
        </div>
        {f'<div class="info-box"><strong>Notes from Reviewer:</strong><br>{notes}</div>' if notes else ''}
        <p>Please log in to the portal to view more details and take any necessary actions.</p>
        <div style="text-align: center;">
            <a href="{os.getenv("FRONTEND_URL", "https://portal.bnr.rw")}/applications/{application_id}" class="btn">View Application</a>
        </div>
    """
    return get_base_template(content)

def get_application_submitted_template(user_fullname: str, application_id: str) -> str:
    content = f"""
        <h2 style="margin-top: 0;">Application Submitted</h2>
        <p>Hello {user_fullname},</p>
        <p>Your application for a bank license has been successfully submitted and is now in the <span class="highlight">INITIAL_REVIEW</span> stage.</p>
        <div class="info-box">
            <strong>Application ID:</strong> #{application_id}<br>
            <strong>Submitted on:</strong> {os.getenv("CURRENT_DATE", "today")}
        </div>
        <p>Our team will review your submission and you will be notified of any status changes via email.</p>
        <p>You can track the progress of your application at any time by logging into your dashboard.</p>
    """
    return get_base_template(content)

# ─── Email Configuration Mapping ───────────────────────────────────────────────

EMAIL_TEMPLATES = {
    EmailType.ACCOUNT_VERIFICATION: {
        "template": get_account_verification_template,
        "subject": "Verify your BNR Licensing Portal account",
    },
    EmailType.PASSWORD_RESET: {
        "template": get_password_reset_template,
        "subject": "Reset your BNR Portal password",
    },
    EmailType.STAFF_ACCOUNT_CREATED: {
        "template": get_staff_account_created_template,
        "subject": "Welcome to BNR Portal - Staff Account Created",
    },
    EmailType.APPLICATION_SUBMITTED: {
        "template": get_application_submitted_template,
        "subject": "Application Successfully Submitted",
    },
    EmailType.APPLICATION_STATUS_UPDATE: {
        "template": get_application_status_update_template,
        "subject": "Important Update: Your Application Status",
    },
    EmailType.OTP_VERIFICATION: {
        "template": get_otp_verification_template,
        "subject": "Your BNR Portal Verification Code",
    },
}

# ─── Main Send Function ───────────────────────────────────────────────────────

def send_email(
    email_type: EmailType,
    recipient_email: str,
    **kwargs
) -> Any:
    """
    Generic function to send BNR portal emails using Resend.

    Usage:
        send_email(
            email_type=EmailType.ACCOUNT_VERIFICATION,
            recipient_email="applicant@bank.com",
            user_fullname="Jean Doe",
            verification_link="https://portal.bnr.rw/verify?token=..."
        )
    """
    try:
        template_config = EMAIL_TEMPLATES.get(email_type)
        if not template_config:
            raise ValueError(f"Invalid email type: {email_type}")

        from typing import Callable, cast
        template_fn = cast(Callable, template_config["template"])

        # Filter kwargs to match template function signature
        sig = inspect.signature(template_fn)
        valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

        email_body = template_fn(**valid_kwargs)

        params: resend.Emails.SendParams = {
            "from": FROM_EMAIL,
            "to": [recipient_email],
            "subject": str(template_config["subject"]),
            "html": email_body,
        }

        email_response: Any = resend.Emails.send(params)
        return email_response

    except Exception as e:
        # In production, you might want to log this to Sentry/CloudWatch
        print(f"FAILED TO SEND EMAIL: {str(e)}")
        raise Exception(f"Error sending email: {str(e)}")

# Backward compatibility util
async def send_email_util(email_data: EmailSchema):
    """Simple utility to send raw HTML emails via Resend"""
    try:
        params: resend.Emails.SendParams = {
            "from": FROM_EMAIL,
            "to": email_data.email,
            "subject": email_data.subject,
            "html": email_data.body,
        }
        return resend.Emails.send(params)
    except Exception as e:
        raise Exception(f"Error sending email: {str(e)}")
