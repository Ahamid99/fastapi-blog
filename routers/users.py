from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import PostResponse, UserCreate, UserPublic, UserPrivate, Token, UserUpdate

from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm

from auth import create_access_token, hash_password, oauth2_scheme, verify_access_token, verify_password

from config import settings

# create router instance
router = APIRouter()

# creating user
@router.post(
        "", # inside quotes here are postfix on top of  what is defined in mian.py
        response_model= UserPrivate,
        status_code=status.HTTP_201_CREATED
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)] ):
    result = await db.execute(
        select(models.User)
        .where(func.lower(models.User.username) == user.username.lower())
    )
    # grabs the first user if existing else None
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    # check if email is duplicate
    result = await db.execute(
        select(models.User)
        .where(func.lower(models.User.email) == user.email.lower()),
    )
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists."
        )

    new_user = models.User(
        username = user.username,
        email=user.email.lower(),
        password_hash=hash_password(user.password),
    )

    # add to db
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user) #reloads the object from the db

    return new_user # pydantic will automatically convet it to UserResponse Obj


## login_for_access_token
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    # Look up user by email (case-insensitive)
    # Note: OAuth2PasswordRequestForm uses "username" field, but we treat it as email
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == form_data.username.lower(),
        ),
    )
    user = result.scalars().first()

    # Verify user exists and password is correct
    # Don't reveal which one failed (security best practice)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token with user id as subject
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


## get_current_user
@router.get("/me", response_model=UserPrivate)
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the currently authenticated user."""
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate user_id is a valid integer (defense against malformed JWT)
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(models.User).where(models.User.id == user_id_int),
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# get user
@router.get("/{user_id}", response_model=UserPublic)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found")


# UPDATING User endpoints
@router.patch("/{user_id}", response_model=UserPrivate)
async def update_user(user_id: int,
                     user_update: UserUpdate,
                     db: Annotated[AsyncSession, Depends(get_db)]):
    # check if user exists
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                        detail="User not found")

    # now check if updated username is not null and not the same
    if user_update.username is not None and user_update.username.lower() != user.username.lower():
        result = await db.execute( # now check it against DB
            select(models.User)
            .where(func.lower(models.User.username) == user_update.username.lower()),
        )
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists",
            )
    #Email
    if user_update.email is not None and user_update.email.lower() != user.email.lower():
        result = await db.execute(
            select(models.User)
            .where(func.lower(models.User.email) == user_update.email.lower()),
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )
        
    # update only the fields that are provided
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.image_file is not None:
        user.image_file = user_update.image_file

    await db.commit()
    await db.refresh(user)
    return user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    # Note: the cascade set up in models will auto delete posts
    await db.delete(user)
    await db.commit()

# get posts by user
@router.get("/{user_id}/posts", response_model=list[PostResponse])
async def get_user_posts(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    # check if the user Exists first
    result = await db.execute(
        select(models.User)
        .where(models.User.id == user_id)
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="User not found")

    result = await db.execute(select(models.Post)
                              .options(selectinload(models.Post.author))
                              .where(models.Post.user_id == user_id)
                              .order_by(models.Post.date_posted.desc())
                              )
    posts = result.scalars().all()
    return posts
