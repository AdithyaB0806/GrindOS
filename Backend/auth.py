from jose import jwt
from datetime import datetime,timedelta
import os
from dotenv import load_dotenv

load_dotenv()
EXPIRE = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
SECRET_KEY=os.getenv("SECRET_KEY")
ALGORITHM=os.getenv("ALGORITHM")
EXPIRE=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

def create_access_token(data:dict):

    to_encode=data.copy()

    expire=datetime.utcnow()+timedelta(minutes=EXPIRE)

    to_encode.update({"exp":expire})

    token=jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    

    return token
print(os.getenv("SECRET_KEY"))
print(os.getenv("ALGORITHM"))
print(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
