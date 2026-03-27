from __future__ import annotations

from typing import Optional

from langbot_plugin.api.entities.builtin.provider.message import (  # noqa: F401
    ContentElement,
    FunctionCall,
    ImageURLContentObject,
    Message as SDKMessage,
    MessageChunk,
    ToolCall,
)


class Message(SDKMessage):
    timestamp: Optional[str] = None
