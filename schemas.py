from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, EmailStr


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    email: EmailStr = Field(max_length=120)

class UserCreate(UserBase):
    pass 

class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=120)
    image_file: str | None = Field(default=None, min_length=1, max_length=200)

class UserResponse(UserBase):
    #Tells Pydantic it can create this model from an object's attributes 
    # (e.g. a SQLAlchemy database model), not just a dictionary.
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_file: str | None
    image_path: str 


class PostBase(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1)

class PostCreate(PostBase):
    user_id: int # temporary

class PostUpdate(BaseModel):
    title: str | None = Field(default= None, min_length=1, max_length=100)
    content: str | None = Field(default=None, min_length=1)

class PostResponse(PostBase):
    model_config = ConfigDict(from_attributes=True)

    # fields we will add on top of inheried from PostBase
    id: int
    user_id: int 
    date_posted: datetime
    author: UserResponse