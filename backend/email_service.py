"""
Email service using SendGrid for transactional emails
"""

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


class EmailService:
    """Email service using SendGrid API"""
    
    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY')
        self.from_email = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@stockmatrix.com')
        self.from_name = os.getenv('SENDGRID_FROM_NAME', 'Stock Matrix')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        
        if not self.api_key:
            print("⚠️ WARNING: SENDGRID_API_KEY not set in environment variables")
        
        self.sg = SendGridAPIClient(self.api_key) if self.api_key else None
        
        # Get templates directory
        self.templates_dir = Path(__file__).parent / 'email_templates'
    
    async def send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Generic email sending function
        
        Args:
            to_email: Recipient email address
            subject: Email subject line
            html_content: HTML content of the email
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.sg:
            print("❌ SendGrid client not initialized (API key missing)")
            return False
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            response = self.sg.send(message)
            
            if response.status_code == 202:
                print(f"✅ Email sent successfully to {to_email}")
                return True
            else:
                print(f"⚠️ Unexpected status code: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error sending email to {to_email}: {e}")
            return False
    
    def _load_template(self, template_name: str) -> str:
        """Load email template from file"""
        template_path = self.templates_dir / template_name
        
        if template_path.exists():
            with open(template_path, 'r') as f:
                return f.read()
        else:
            print(f"⚠️ Template not found: {template_name}, using fallback")
            return ""
    
    async def send_verification_email(self, email: str, username: str, token: str) -> bool:
        """
        Send email verification link
        
        Args:
            email: User's email address
            username: User's username
            token: Verification token
            
        Returns:
            True if sent successfully, False otherwise
        """
        verify_url = f"{self.frontend_url}/verify-email?token={token}"
        subject = "Verify Your Email - Stock Matrix"
        
        # Load HTML template
        html_content = self._load_template('verification.html')
        
        # If template not found, use inline HTML
        if not html_content:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #0a0a0a; color: #ffffff;">
                <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 10px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 255, 0, 0.1);">
                        <h1 style="color: #00ff41; margin: 0 0 20px 0; font-size: 28px;">Welcome to Stock Matrix</h1>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                            Hi {username},
                        </p>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                            Thank you for registering! Please verify your email address to activate your account and start analyzing stocks.
                        </p>
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{verify_url}" style="display: inline-block; background-color: #00ff41; color: #0a0a0a; text-decoration: none; padding: 15px 40px; border-radius: 5px; font-size: 16px; font-weight: bold; box-shadow: 0 2px 4px rgba(0, 255, 65, 0.3);">
                                Verify Email Address
                            </a>
                        </div>
                        <p style="color: #808080; font-size: 14px; line-height: 1.6; margin-top: 30px;">
                            This link will expire in 24 hours. If you didn't create an account, you can safely ignore this email.
                        </p>
                        <p style="color: #808080; font-size: 14px; line-height: 1.6; margin-top: 20px;">
                            Or copy and paste this URL into your browser:<br>
                            <span style="color: #00ff41; word-break: break-all;">{verify_url}</span>
                        </p>
                    </div>
                    <div style="text-align: center; margin-top: 30px; color: #606060; font-size: 12px;">
                        <p>Stock Matrix - See Through The Market</p>
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            # Replace placeholders in template
            html_content = html_content.replace('{{username}}', username)
            html_content = html_content.replace('{{verify_url}}', verify_url)
        
        return await self.send_email(email, subject, html_content)
    
    async def send_welcome_email(self, email: str, username: str) -> bool:
        """
        Send welcome email after successful verification
        
        Args:
            email: User's email address
            username: User's username
            
        Returns:
            True if sent successfully, False otherwise
        """
        subject = "Welcome to Stock Matrix!"
        
        # Load HTML template
        html_content = self._load_template('welcome.html')
        
        # If template not found, use inline HTML
        if not html_content:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #0a0a0a; color: #ffffff;">
                <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 10px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 255, 0, 0.1);">
                        <h1 style="color: #00ff41; margin: 0 0 20px 0; font-size: 28px;">🎉 Account Verified!</h1>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                            Hi {username},
                        </p>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                            Your email has been successfully verified! You can now access all features of Stock Matrix.
                        </p>
                        <h2 style="color: #00ff41; font-size: 20px; margin-top: 30px; margin-bottom: 15px;">What's Next?</h2>
                        <ul style="color: #e0e0e0; font-size: 16px; line-height: 1.8; padding-left: 20px;">
                            <li>Track real-time stock prices and charts</li>
                            <li>Analyze technical indicators (MACD, RSI, Bollinger Bands)</li>
                            <li>Review fundamental data and company metrics</li>
                            <li>Stay updated with news and sentiment analysis</li>
                        </ul>
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{self.frontend_url}" style="display: inline-block; background-color: #00ff41; color: #0a0a0a; text-decoration: none; padding: 15px 40px; border-radius: 5px; font-size: 16px; font-weight: bold; box-shadow: 0 2px 4px rgba(0, 255, 65, 0.3);">
                                Start Analyzing Stocks
                            </a>
                        </div>
                        <p style="color: #808080; font-size: 14px; line-height: 1.6; margin-top: 30px;">
                            If you have any questions or need help, feel free to reach out to our support team.
                        </p>
                    </div>
                    <div style="text-align: center; margin-top: 30px; color: #606060; font-size: 12px;">
                        <p>Stock Matrix - See Through The Market</p>
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            # Replace placeholders
            html_content = html_content.replace('{{username}}', username)
            html_content = html_content.replace('{{frontend_url}}', self.frontend_url)
        
        return await self.send_email(email, subject, html_content)
    
    async def send_password_reset_email(self, email: str, username: str, token: str) -> bool:
        """
        Send password reset link
        
        Args:
            email: User's email address
            username: User's username
            token: Password reset token
            
        Returns:
            True if sent successfully, False otherwise
        """
        reset_url = f"{self.frontend_url}/reset-password?token={token}"
        subject = "Reset Your Password - Stock Matrix"
        
        # Load HTML template
        html_content = self._load_template('password_reset.html')
        
        # If template not found, use inline HTML
        if not html_content:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
            </head>
            <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #0a0a0a; color: #ffffff;">
                <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
                    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); border-radius: 10px; padding: 40px; box-shadow: 0 4px 6px rgba(0, 255, 0, 0.1);">
                        <h1 style="color: #00ff41; margin: 0 0 20px 0; font-size: 28px;">Reset Your Password</h1>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 20px;">
                            Hi {username},
                        </p>
                        <p style="color: #e0e0e0; font-size: 16px; line-height: 1.6; margin-bottom: 30px;">
                            We received a request to reset your password. Click the button below to create a new password.
                        </p>
                        <div style="text-align: center; margin: 40px 0;">
                            <a href="{reset_url}" style="display: inline-block; background-color: #00ff41; color: #0a0a0a; text-decoration: none; padding: 15px 40px; border-radius: 5px; font-size: 16px; font-weight: bold; box-shadow: 0 2px 4px rgba(0, 255, 65, 0.3);">
                                Reset Password
                            </a>
                        </div>
                        <p style="color: #808080; font-size: 14px; line-height: 1.6; margin-top: 30px;">
                            This link will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email.
                        </p>
                        <p style="color: #808080; font-size: 14px; line-height: 1.6; margin-top: 20px;">
                            Or copy and paste this URL into your browser:<br>
                            <span style="color: #00ff41; word-break: break-all;">{reset_url}</span>
                        </p>
                    </div>
                    <div style="text-align: center; margin-top: 30px; color: #606060; font-size: 12px;">
                        <p>Stock Matrix - See Through The Market</p>
                    </div>
                </div>
            </body>
            </html>
            """
        else:
            # Replace placeholders
            html_content = html_content.replace('{{username}}', username)
            html_content = html_content.replace('{{reset_url}}', reset_url)
        
        return await self.send_email(email, subject, html_content)


# Create a global email service instance
email_service = EmailService()
