from pydantic import BaseModel


class ServerSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 4000


server_settings = ServerSettings()
