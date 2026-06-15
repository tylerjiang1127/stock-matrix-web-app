"""
Authentication utilities for password hashing, token generation, and validation
"""

from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import secrets
import re
from typing import Optional, Tuple

# Password hashing context with bcrypt settings
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__ident="2b"  # Use bcrypt 2b version for better compatibility
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    # Bcrypt has a maximum password length of 72 bytes
    # Truncate if necessary (shouldn't happen with normal passwords)
    if len(password.encode('utf-8')) > 72:
        # Hash the password first with SHA256 if it's too long
        import hashlib
        password = hashlib.sha256(password.encode('utf-8')).hexdigest()
    
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False


def generate_verification_token() -> str:
    """
    Generate a secure random token for email verification or password reset
    
    Returns:
        64-character random token
    """
    return secrets.token_urlsafe(48)  # 48 bytes = 64 characters in urlsafe base64


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength
    Requirements:
    - At least 8 characters
    - At most 50 characters (practical limit)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if len(password) > 50:
        return False, "Password must be at most 50 characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    
    return True, None


def validate_email(email: str) -> bool:
    """
    Validate email format using regex
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> Tuple[bool, Optional[str]]:
    """
    Validate username format
    Requirements:
    - 3-50 characters
    - Alphanumeric, underscore, and hyphen only
    - Must start with a letter
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    
    if len(username) > 50:
        return False, "Username must be at most 50 characters long"
    
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', username):
        return False, "Username must start with a letter and contain only letters, numbers, underscores, and hyphens"
    
    return True, None


def create_token_expiry(hours: int = 24) -> datetime:
    """
    Create an expiry datetime for a token (timezone-aware)
    
    Args:
        hours: Number of hours until expiry (default 24)
        
    Returns:
        Timezone-aware datetime object for token expiry (UTC)
    """
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def is_token_expired(expires_at: datetime) -> bool:
    """
    Check if a token has expired
    
    Args:
        expires_at: Expiry datetime of the token (should be timezone-aware)
        
    Returns:
        True if expired, False otherwise
    """
    # Ensure current time is timezone-aware (UTC)
    now = datetime.now(timezone.utc)
    
    # If expires_at is naive (no timezone), make it UTC-aware
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    return now > expires_at
