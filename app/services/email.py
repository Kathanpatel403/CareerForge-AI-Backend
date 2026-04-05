import logging
from fastapi import BackgroundTasks
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from app.core.config import settings

logger = logging.getLogger(__name__)

# Validate that email configurations are essentially set before initializing config fully
# Pydantic-settings handles loading these, but fastapi_mail requires actual strings
try:
    mail_config = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM or "noreply@ai-career-copilot.com",
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=bool(settings.MAIL_USERNAME and settings.MAIL_PASSWORD),
        VALIDATE_CERTS=True
    )
    fm = FastMail(mail_config)
except Exception as e:
    logger.warning(f"Failed to initialize email client. Emails will not be sent. Error: {e}")
    fm = None

def send_registration_email(background_tasks: BackgroundTasks, email: str, name: str):
    """
    Queue a welcome email to newly registered users in the background.
    """
    if not fm or not settings.MAIL_USERNAME:
        logger.warning(f"Email service not configured. Skipped sending welcome email to {email}")
        return

    message = MessageSchema(
        subject="Welcome to AI Career Copilot!",
        recipients=[email],
        body=f"<h2>Hello {name},</h2><p>Welcome to AI Career Copilot! We're excited to help you supercharge your career journey.</p>",
        subtype=MessageType.html
    )
    
    logger.info(f"Prepared registration email for {email}")
    background_tasks.add_task(fm.send_message, message)
    logger.info(f"Background task added for registration email to {email}")

def send_password_reset_email(background_tasks: BackgroundTasks, email: str, token: str):
    """
    Queue a password reset email in the background.
    """
    if not fm or not settings.MAIL_USERNAME:
        logger.warning(f"Email service not configured. Skipped sending reset email to {email}. Token: {token}")
        return

    # Assuming frontend is hosted locally on 5173 for dev, normally this would come from a FRONTEND_URL setting
    reset_link = f"http://localhost:5173/reset-password?token={token}"
    
    message = MessageSchema(
        subject="Password Reset Request",
        recipients=[email],
        body=f"<h2>Password Reset</h2><p>Click the link below to reset your password:</p><p><a href='{reset_link}'>Reset Password</a></p><p>If you didn't request this, you can safely ignore this email.</p>",
        subtype=MessageType.html
    )
    
    logger.info(f"Prepared password reset email for {email}")
    background_tasks.add_task(fm.send_message, message)
    logger.info(f"Background task added for reset email to {email}")
