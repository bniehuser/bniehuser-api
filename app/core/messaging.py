import json
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class SocketScope(Enum):
    PUBLIC = 'public'
    PRIVATE = 'private'
    SYSTEM = 'system'


class SocketSource(Enum):
    SERVER = 'server'
    CLIENT = 'client'
    BOT = 'bot'


PUBLIC_ENUMS = {
    'SocketScope': SocketScope,
    'SocketSource': SocketSource,
}


class EnumEncoder(json.JSONEncoder):
    def default(self, obj):
        if type(obj) in PUBLIC_ENUMS.values():
            return {"__enum__": str(obj)}
        return json.JSONEncoder.default(self, obj)


def as_enum(d):
    if "__enum__" in d:
        name, member = d["__enum__"].split(".")
        return getattr(PUBLIC_ENUMS[name], member)
    else:
        return d


class SocketMessage(BaseModel):
    scope: SocketScope = SocketScope.PUBLIC
    source: SocketSource = SocketSource.SERVER
    type: Optional[str] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    message: str

    def to_str(self):
        return json.dumps(self.dict(), cls=EnumEncoder)

    @staticmethod
    def from_str(s: str):
        data = json.loads(s, object_hook=as_enum)
        if 'scope' in data and type(data['scope']) is str:
            data['scope'] = SocketScope(data['scope'])
        if 'source' in data and type(data['source']) is str:
            data['source'] = SocketSource(data['source'])
        return SocketMessage(**data)
