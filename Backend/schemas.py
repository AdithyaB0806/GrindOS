from pydantic import BaseModel,EmailStr

class Register(BaseModel):
    name:str
    email:EmailStr
    password:str


class Login(BaseModel):
    email:EmailStr
    password:str


class Token(BaseModel):
    access_token:str
    token_type:str