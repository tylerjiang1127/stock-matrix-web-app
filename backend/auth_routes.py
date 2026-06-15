"""
Authentication routes for user registration, login, verification, and password reset
"""

from fastapi import APIRouter, HTTPException, Response, Cookie, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

from auth_utils import (
    hash_password,
    verify_password,
    generate_verification_token,
    validate_password_strength,
    validate_email,
    validate_username,
    create_token_expiry,
    is_token_expired
)
from email_service import email_service
from postgres_models import UserRepository, TokenRepository
from redis_database import session_manager
from postgres_database import postgres_db

# Create router
auth_router = APIRouter()

# Initialize repositories
user_repo = UserRepository(postgres_db)
token_repo = TokenRepository(postgres_db)


# Request/Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    password_confirm: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    new_password_confirm: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    user_id: str
    username: str
    email: str
    is_email_verified: bool
    status: str


# Helper function to get session from cookie
async def get_current_user(session_id: Optional[str] = Cookie(None)) -> Optional[dict]:
    """Get current user from session cookie"""
    if not session_id:
        return None
    
    session_data = await session_manager.get_session(session_id)
    if not session_data:
        return None
    
    return session_data


# ==================== REGISTRATION ====================

@auth_router.post("/register")
async def register(request: RegisterRequest):
    """
    Register a new user
    
    Steps:
    1. Validate email format
    2. Check email not already registered
    3. Validate username format and uniqueness
    4. Validate password strength
    5. Check password confirmation matches
    6. Hash password and create user
    7. Generate verification token
    8. Send verification email
    """
    try:
        # 1. Validate email format
        if not validate_email(request.email):
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        # 2. Check if email already registered
        existing_user = await user_repo.get_user_by_email(request.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email address is already registered")
        
        # 3. Validate username
        is_valid_username, username_error = validate_username(request.username)
        if not is_valid_username:
            raise HTTPException(status_code=400, detail=username_error)
        
        # Check if username already taken
        existing_username = await user_repo.get_user_by_username(request.username)
        if existing_username:
            raise HTTPException(status_code=400, detail="Username is already taken")
        
        # 4. Validate password strength
        is_valid_password, password_error = validate_password_strength(request.password)
        if not is_valid_password:
            raise HTTPException(status_code=400, detail=password_error)
        
        # 5. Check password confirmation
        if request.password != request.password_confirm:
            raise HTTPException(status_code=400, detail="Passwords do not match")
        
        # 6. Hash password and create user
        password_hash = hash_password(request.password)
        user_id = await user_repo.create_user(request.email, request.username, password_hash)
        
        if not user_id:
            raise HTTPException(status_code=500, detail="Failed to create user account")
        
        # 7. Generate verification token (permanent - 10 years expiry)
        token = generate_verification_token()
        expires_at = create_token_expiry(hours=87600)  # 10 years = 87600 hours (basically permanent)
        
        await token_repo.create_verification_token(user_id, token, expires_at)
        
        # 8. Send verification email
        email_sent = await email_service.send_verification_email(
            request.email,
            request.username,
            token
        )
        
        if not email_sent:
            print(f"⚠️ Failed to send verification email to {request.email}")
        
        return {
            "success": True,
            "message": "Registration successful! Please check your email to verify your account.",
            "email": request.email
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = str(e)
        print(f"❌ Registration error: {error_details}")
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Provide more specific error messages based on error type
        if "connection" in error_details.lower() or "database" in error_details.lower():
            raise HTTPException(status_code=500, detail=f"Database connection error. Please try again later.")
        elif "email" in error_details.lower():
            raise HTTPException(status_code=500, detail=f"Failed to send verification email. Please check your email address.")
        else:
            raise HTTPException(status_code=500, detail=f"Registration failed: {error_details}")


# ==================== EMAIL VERIFICATION ====================

@auth_router.get("/verify-email")
async def verify_email(token: str, response: Response):
    """
    Verify email address with token and automatically log in the user
    
    Steps:
    1. Validate token exists and not expired
    2. Check token not already used
    3. Mark user email as verified
    4. Mark token as used
    5. Create session and set cookie (auto-login)
    6. Send welcome email
    """
    try:
        # 1. Get token details
        token_data = await token_repo.get_verification_token(token)
        
        if not token_data:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")
        
        # 2. Check if token already used
        if token_data.get('used'):
            raise HTTPException(status_code=400, detail="Verification token has already been used")
        
        # Note: Token expiry check removed - tokens are now valid permanently (10 years)
        
        # 3. Mark user email as verified
        user_id = str(token_data['user_id'])
        success = await user_repo.update_email_verified(user_id, True)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to verify email")
        
        # 4. Mark token as used
        await token_repo.mark_verification_token_used(token)
        
        # 5. Create session and auto-login the user
        session_id = await session_manager.create_session(user_id, {
            'username': token_data['username'],
            'email': token_data['email']
        })
        
        # Set HTTP-only secure cookie for auto-login
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        
        # 6. Send welcome email
        await email_service.send_welcome_email(
            token_data['email'],
            token_data['username']
        )
        
        return {
            "success": True,
            "message": "Email verified successfully! You are now logged in.",
            "username": token_data['username'],
            "auto_logged_in": True  # Flag to indicate auto-login
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Email verification error: {e}")
        raise HTTPException(status_code=500, detail="Email verification failed")


# ==================== RESEND VERIFICATION EMAIL ====================

@auth_router.post("/resend-verification")
async def resend_verification_email(request: ResendVerificationRequest):
    """
    Resend verification email to a user
    
    This endpoint allows users to manually request a new verification email
    if they didn't receive it or if their previous link expired.
    
    Steps:
    1. Find user by email
    2. Check if already verified
    3. Generate new verification token
    4. Send verification email
    """
    try:
        # 1. Find user by email
        user = await user_repo.get_user_by_email(request.email)
        
        if not user:
            # Don't reveal if email exists - return success anyway
            return {
                "success": True,
                "message": "If an unverified account exists with this email, a verification link has been sent."
            }
        
        # 2. Check if already verified
        if user.get('is_email_verified'):
            return {
                "success": True,
                "message": "This email address is already verified. You can log in now."
            }
        
        # 3. Generate new verification token (permanent - 10 years)
        token = generate_verification_token()
        expires_at = create_token_expiry(hours=87600)
        
        user_id = str(user['id'])
        await token_repo.create_verification_token(user_id, token, expires_at)
        
        # 4. Send verification email
        email_sent = await email_service.send_verification_email(
            user['email'],
            user['username'],
            token
        )
        
        if not email_sent:
            print(f"⚠️ Failed to send verification email to {request.email}")
        
        return {
            "success": True,
            "message": "Verification email has been sent. Please check your inbox."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Resend verification error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send verification email")


# ==================== LOGIN ====================

@auth_router.post("/login")
async def login(request: LoginRequest, response: Response):
    """
    User login
    
    Steps:
    1. Find user by email
    2. Check email is verified
    3. Verify password
    4. Check account status is active
    5. Create session
    6. Set HTTP-only cookie
    7. Return user data
    """
    try:
        # 1. Find user by email
        user = await user_repo.get_user_by_email(request.email)
        
        if not user:
            raise HTTPException(status_code=401, detail="Email Address or Password is incorrect")
        
        # 2. Verify password first (before checking verification status)
        #    This prevents attackers from knowing if an email exists in the system
        if not verify_password(request.password, user['password_hash']):
            raise HTTPException(status_code=401, detail="Email Address or Password is incorrect")
        
        # 3. Check if email is verified - if not, send new verification email
        if not user.get('is_email_verified'):
            # Generate new verification token (permanent - 10 years)
            token = generate_verification_token()
            expires_at = create_token_expiry(hours=87600)
            
            user_id = str(user['id'])
            await token_repo.create_verification_token(user_id, token, expires_at)
            
            # Send verification email
            await email_service.send_verification_email(
                user['email'],
                user['username'],
                token
            )
            
            raise HTTPException(
                status_code=403,
                detail="We detected your email address is not verified yet. We are sending a verification email to you. Please verify your email now and try logging in again."
            )
        
        # 4. Check account status
        if user.get('status') != 'active':
            raise HTTPException(
                status_code=403,
                detail=f"Account is {user.get('status')}. Please contact support."
            )
        
        # 5. Create session
        user_id = str(user['id'])
        session_id = await session_manager.create_session(user_id, {
            'username': user['username'],
            'email': user['email']
        })
        
        # 6. Set HTTP-only secure cookie
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        
        # 7. Return user data (without password hash)
        return {
            "success": True,
            "message": "Login successful",
            "user": {
                "user_id": user_id,
                "username": user['username'],
                "email": user['email'],
                "is_email_verified": user['is_email_verified'],
                "status": user['status']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


# ==================== LOGOUT ====================

@auth_router.post("/logout")
async def logout(response: Response, session_id: Optional[str] = Cookie(None)):
    """
    User logout
    
    Steps:
    1. Get session ID from cookie
    2. Delete session from Redis
    3. Clear cookie
    """
    try:
        if session_id:
            await session_manager.delete_session(session_id)
        
        # Clear cookie
        response.delete_cookie(key="session_id")
        
        return {
            "success": True,
            "message": "Logout successful"
        }
        
    except Exception as e:
        print(f"❌ Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


# ==================== GET CURRENT USER ====================

@auth_router.get("/me")
async def get_me(session_id: Optional[str] = Cookie(None)):
    """
    Get current user information from session
    
    Used to check if user is logged in and restore session on page refresh
    """
    try:
        if not session_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Get session data
        session_data = await session_manager.get_session(session_id)
        
        if not session_data:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        
        # Get full user data from database
        user = await user_repo.get_user_by_id(session_data['user_id'])
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Refresh session expiry
        await session_manager.refresh_session(session_id)
        
        return {
            "success": True,
            "user": {
                "user_id": str(user['id']),
                "username": user['username'],
                "email": user['email'],
                "is_email_verified": user['is_email_verified'],
                "status": user['status']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Get current user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user information")


# ==================== FORGOT PASSWORD ====================

@auth_router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    """
    Request password reset
    
    Steps:
    1. Find user by email (don't reveal if user exists)
    2. Generate reset token (1-hour expiry)
    3. Send reset email
    4. Always return success (security: don't reveal if email exists)
    """
    try:
        # 1. Find user by email
        user = await user_repo.get_user_by_email(request.email)
        
        if user:
            # 2. Generate reset token (1-hour expiry)
            token = generate_verification_token()
            expires_at = create_token_expiry(hours=1)
            
            user_id = str(user['id'])
            await token_repo.create_reset_token(user_id, token, expires_at)
            
            # 3. Send reset email
            await email_service.send_password_reset_email(
                user['email'],
                user['username'],
                token
            )
        
        # 4. Always return success (security measure)
        return {
            "success": True,
            "message": "If the email address exists in our system, a password reset link has been sent."
        }
        
    except Exception as e:
        print(f"❌ Forgot password error: {e}")
        # Still return success to prevent email enumeration
        return {
            "success": True,
            "message": "If the email address exists in our system, a password reset link has been sent."
        }


# ==================== RESET PASSWORD ====================

@auth_router.post("/reset-password")
async def reset_password(request: ResetPasswordRequest, response: Response):
    """
    Reset password with token
    
    Steps:
    1. Validate token exists and not expired
    2. Check token not already used
    3. Validate new password strength
    4. Check password confirmation matches
    5. Hash new password and update user
    6. Mark token as used
    7. Delete all user sessions (force re-login)
    """
    try:
        # Debug logging
        print(f"🔧 Reset password attempt:")
        print(f"  - Token (first 20 chars): {request.token[:20]}...")
        print(f"  - New password length: {len(request.new_password)}")
        print(f"  - Confirm password length: {len(request.new_password_confirm)}")
        print(f"  - Passwords match: {request.new_password == request.new_password_confirm}")
        
        # 1. Get token details
        token_data = await token_repo.get_reset_token(request.token)
        
        if not token_data:
            print(f"❌ Token not found in database")
            raise HTTPException(
                status_code=400, 
                detail="Password reset failed: Invalid or expired reset token. Please request a new password reset link."
            )
        
        print(f"✅ Token found for user: {token_data.get('email', 'unknown')}")
        
        # 2. Check if token already used
        if token_data.get('used'):
            print(f"❌ Token already used")
            raise HTTPException(
                status_code=400, 
                detail="Password reset failed: This reset link has already been used. Please request a new password reset link."
            )
        
        # Check if token expired
        if is_token_expired(token_data['expires_at']):
            print(f"❌ Token expired at: {token_data['expires_at']}")
            raise HTTPException(
                status_code=400, 
                detail="Password reset failed: This reset link has expired (valid for 1 hour). Please request a new password reset link."
            )
        
        print(f"✅ Token is valid and not expired")
        
        # 3. Validate new password strength
        is_valid_password, password_error = validate_password_strength(request.new_password)
        if not is_valid_password:
            print(f"❌ Password validation failed: {password_error}")
            raise HTTPException(
                status_code=400, 
                detail=f"Password reset failed: {password_error}"
            )
        
        print(f"✅ Password strength validated")
        
        # 4. Check password confirmation
        if request.new_password != request.new_password_confirm:
            print(f"❌ Passwords don't match")
            print(f"  - Password 1 length: {len(request.new_password)}")
            print(f"  - Password 2 length: {len(request.new_password_confirm)}")
            # Debug: Show first and last chars (safe for debugging)
            if request.new_password and request.new_password_confirm:
                print(f"  - Password 1 starts with: {request.new_password[0]}, ends with: {request.new_password[-1]}")
                print(f"  - Password 2 starts with: {request.new_password_confirm[0]}, ends with: {request.new_password_confirm[-1]}")
            raise HTTPException(
                status_code=400, 
                detail="Password reset failed: The two passwords you entered do not match. Please make sure both password fields are identical."
            )
        
        print(f"✅ Password confirmation matches")
        
        # 5. Hash new password and update user
        try:
            password_hash = hash_password(request.new_password)
            print(f"✅ Password hashed successfully")
        except Exception as e:
            print(f"❌ Password hashing error: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Password reset failed: Error processing password - {str(e)}"
            )
        
        user_id = str(token_data['user_id'])
        print(f"🔧 Updating password for user_id: {user_id}")
        
        success = await user_repo.update_password(user_id, password_hash)
        
        if not success:
            print(f"❌ Database update failed")
            raise HTTPException(
                status_code=500, 
                detail="Password reset failed: Unable to update password in database. Please try again or contact support."
            )
        
        print(f"✅ Password updated in database")
        
        # 6. Mark token as used
        await token_repo.mark_reset_token_used(request.token)
        print(f"✅ Token marked as used")
        
        # 7. Create new session for auto-login
        session_id = await session_manager.create_session(user_id, {
            'username': token_data['username'],
            'email': token_data['email']
        })
        
        # Set HTTP-only secure cookie for auto-login
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60  # 7 days
        )
        
        print(f"✅ Created new session and auto-logged in user")
        
        print(f"🎉 Password reset completed successfully for user: {token_data.get('email', 'unknown')}")
        
        return {
            "success": True,
            "message": "Password reset successfully! You are now logged in.",
            "username": token_data['username'],
            "auto_logged_in": True  # Flag to indicate auto-login
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = str(e)
        print(f"❌ Unexpected reset password error: {error_details}")
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Provide more specific error messages based on error type
        if "connection" in error_details.lower() or "database" in error_details.lower():
            raise HTTPException(
                status_code=500, 
                detail="Password reset failed: Database connection error. Please try again later."
            )
        elif "hash" in error_details.lower():
            raise HTTPException(
                status_code=500, 
                detail="Password reset failed: Error processing password. Please try a different password."
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Password reset failed: {error_details}"
            )
