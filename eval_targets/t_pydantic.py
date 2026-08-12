from pydantic import BaseModel

class User(BaseModel):
    name: str

user = User(name="x")
data = user.dict()
