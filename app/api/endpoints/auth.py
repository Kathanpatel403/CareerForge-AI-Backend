from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, UploadFile, File, Form
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token, ForgotPassword, ResetPassword, ChangePassword, UpdateProfile
from app.schemas.response import BaseResponse
from app.core.security import verify_password, get_password_hash, create_access_token
from app.api.deps import get_current_user
from app.core.config import settings
from datetime import timedelta, datetime
import uuid
import base64
from app.services.email import send_registration_email, send_password_reset_email

router = APIRouter()

@router.post("/signup", response_model=BaseResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def signup(user_in: UserCreate, background_tasks: BackgroundTasks):
    user = await User.find_one(User.email == user_in.email)
    if user:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    new_user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    await new_user.insert()
    
    user_response = UserResponse(
        id=str(new_user.id),
        email=new_user.email,
        full_name=new_user.full_name,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )
    
    # Send welcome email via background worker
    send_registration_email(background_tasks, new_user.email, new_user.full_name)
    
    return BaseResponse(success=True, message="User created successfully", data=user_response)

@router.post("/login", response_model=BaseResponse[Token])
async def login(user_in: UserLogin):
    user = await User.find_one(User.email == user_in.email)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    try:
        is_valid = verify_password(user_in.password, user.hashed_password)
    except Exception:
        is_valid = False

    if not is_valid:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=int(settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )
    return BaseResponse(
        success=True, 
        message="Login successful", 
        data=Token(access_token=access_token, token_type="bearer")
    )

@router.get("/profile", response_model=BaseResponse[UserResponse])
async def profile(current_user: User = Depends(get_current_user)):
    user_response = UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        profile_picture=current_user.profile_picture,
        created_at=current_user.created_at
    )
    return BaseResponse(success=True, message="Profile retrieved successfully", data=user_response)

@router.post("/logout", response_model=BaseResponse)
async def logout(current_user: User = Depends(get_current_user)):
    # JWT is stateless by design. We usually log out by throwing away token on client-side.
    return BaseResponse(success=True, message="Logout successful")

@router.post("/forgot-password", response_model=BaseResponse)
async def forgot_password(req: ForgotPassword, background_tasks: BackgroundTasks):
    user = await User.find_one(User.email == req.email)
    if not user:
        # Prevent email enumeration attacks
        return BaseResponse(success=True, message="If your email is registered, you will receive a reset link.")
    
    # Generate a secure reset token inside the database
    reset_token = f"reset-{uuid.uuid4()}"
    user.reset_token = reset_token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    await user.save()
    
    # Send email in background
    send_password_reset_email(background_tasks, req.email, reset_token)
    
    # For now, print in dev logs as fallback
    print(f"Password reset token for {req.email}: {reset_token}")
    
    return BaseResponse(
        success=True, 
        message="If your email is registered, you will receive a reset link.",
        data={"_dev_token": reset_token} # Send in response only for debug mode
    )

@router.post("/reset-password", response_model=BaseResponse)
async def reset_password(req: ResetPassword):
    if not req.token:
         raise HTTPException(status_code=400, detail="Invalid token")
    
    user = await User.find_one(User.reset_token == req.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
        
    if user.reset_token_expires and user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")

    user.hashed_password = get_password_hash(req.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.updated_at = datetime.utcnow()
    await user.save()
    
    return BaseResponse(success=True, message="Password reset successfully")

@router.post("/change-password", response_model=BaseResponse)
async def change_password(req: ChangePassword, current_user: User = Depends(get_current_user)):
    if req.new_password != req.confirm_new_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
        
    try:
        is_valid = verify_password(req.current_password, current_user.hashed_password)
    except Exception:
        is_valid = False
        
    if not is_valid:
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    current_user.hashed_password = get_password_hash(req.new_password)
    current_user.updated_at = datetime.utcnow()
    await current_user.save()
    
    return BaseResponse(success=True, message="Password changed successfully")

from typing import Optional

@router.post("/update-profile", response_model=BaseResponse[UserResponse])
async def update_profile(
    full_name: Optional[str] = Form(None),
    profile_picture: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user)
):
    if full_name:
        current_user.full_name = full_name
        
    if profile_picture:
        # Check size <= 1MB
        file_content = await profile_picture.read()
        if len(file_content) > 1 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Profile picture size must be under 1 MB")
            
        # Convert to Base64
        base64_encoded = base64.b64encode(file_content).decode("utf-8")
        # Prepend content type
        content_type = profile_picture.content_type or "image/jpeg"
        current_user.profile_picture = f"data:{content_type};base64,{base64_encoded}"
        
    current_user.updated_at = datetime.utcnow()
    await current_user.save()
    
    user_response = UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        profile_picture=current_user.profile_picture,
        created_at=current_user.created_at
    )
    
    return BaseResponse(success=True, message="Profile updated successfully", data=user_response)
