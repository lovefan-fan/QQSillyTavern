from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

from langbot_plugin.api.definition.plugin import BasePlugin as SDKBasePlugin
from langbot_plugin.api.entities import context as sdk_context
from langbot_plugin.api.entities.builtin.platform import message as platform_message


def register(**metadata):
    def decorator(cls):
        cls._legacy_register_metadata = metadata
        return cls

    return decorator


def handler(event_type):
    def decorator(func):
        func._legacy_event_type = event_type
        return func

    return decorator


class _LoggerProxy:
    def __init__(self) -> None:
        self._logger = logging.getLogger("QQSillyTavern")

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    def debug(self, message: str) -> None:
        self._logger.debug(message)


@dataclass
class _ProviderConfigProxy:
    data: dict[str, Any]


class _LegacyRequester:
    def __init__(self, plugin: "BasePlugin", llm_model_uuid: str) -> None:
        self._plugin = plugin
        self._llm_model_uuid = llm_model_uuid

    async def call(self, query, model, messages):
        return await self._plugin.invoke_llm(self._llm_model_uuid, messages)


class _LegacyModel:
    def __init__(self, plugin: "BasePlugin", llm_model_uuid: str) -> None:
        self.llm_model_uuid = llm_model_uuid
        self.name = llm_model_uuid
        self.requester = _LegacyRequester(plugin, llm_model_uuid)


class LegacyModelManager:
    def __init__(self, plugin: "BasePlugin", provider_cfg: _ProviderConfigProxy) -> None:
        self._plugin = plugin
        self._provider_cfg = provider_cfg

    async def get_model_by_name(self, name: Optional[str]):
        models = await self._plugin.get_llm_models()
        if not models:
            raise RuntimeError("No LLM models are available in the current LangBot runtime.")

        selected = name if name and name in models else models[0]
        self._provider_cfg.data["model"] = selected
        return _LegacyModel(self._plugin, selected)


class _AppProxy:
    def __init__(self, plugin: "BasePlugin") -> None:
        self.logger = _LoggerProxy()
        self.provider_cfg = _ProviderConfigProxy(data={})
        self.model_mgr = LegacyModelManager(plugin, self.provider_cfg)


class BasePlugin(SDKBasePlugin):
    def __init__(self, host: Optional["APIHost"] = None):
        super().__init__()
        self.host = host or self
        self.ap = _AppProxy(self)
        self.model_mgr = self.ap.model_mgr
        self.provider_cfg = self.ap.provider_cfg


APIHost = BasePlugin


class _QueryProxy:
    def __init__(self, query: Any) -> None:
        object.__setattr__(self, "_query", query)

    def __getattr__(self, item: str) -> Any:
        value = getattr(self._query, item)
        if item == "launcher_type" and hasattr(value, "value"):
            return value.value
        return value

    def __setattr__(self, key: str, value: Any) -> None:
        setattr(self._query, key, value)


class _EventProxy:
    def __init__(self, event: Any) -> None:
        object.__setattr__(self, "_event", event)
        query = getattr(event, "query", None)
        object.__setattr__(self, "_query_proxy", _QueryProxy(query) if query is not None else None)

    def __getattr__(self, item: str) -> Any:
        if item == "query":
            return self._query_proxy
        return getattr(self._event, item)

    def __setattr__(self, key: str, value: Any) -> None:
        setattr(self._event, key, value)


class EventContext:
    def __init__(
        self,
        event_context: sdk_context.EventContext,
        plugin: Optional[BasePlugin] = None,
    ) -> None:
        self._event_context = event_context
        self.plugin = plugin
        self.event = _EventProxy(event_context.event)
        self._pending_replies: list[platform_message.MessageChain] = []

    @classmethod
    def from_sdk(
        cls,
        event_context: sdk_context.EventContext,
        plugin: Optional[BasePlugin] = None,
    ) -> "EventContext":
        return cls(event_context=event_context, plugin=plugin)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._event_context, item)

    async def reply(
        self, message_chain: platform_message.MessageChain, quote_origin: bool = False
    ):
        return await self._event_context.reply(message_chain, quote_origin=quote_origin)

    def add_return(self, action: str, payload: list[Any]) -> None:
        if action != "reply":
            return

        for item in payload:
            message_chain = self._convert_to_message_chain(item)
            if message_chain is not None:
                self._pending_replies.append(message_chain)

    def _convert_to_message_chain(
        self, item: Any
    ) -> Optional[platform_message.MessageChain]:
        if item is None:
            return None

        if isinstance(item, platform_message.MessageChain):
            return item

        if hasattr(item, "get_content_platform_message_chain"):
            return item.get_content_platform_message_chain()

        if isinstance(item, str):
            return platform_message.MessageChain([platform_message.Plain(text=item)])

        return platform_message.MessageChain([platform_message.Plain(text=str(item))])

    def prevent_default(self) -> None:
        self._event_context.prevent_default()

    def prevent_postorder(self) -> None:
        self._event_context.prevent_postorder()

    async def flush(self) -> None:
        for message_chain in self._pending_replies:
            await self._event_context.reply(message_chain)
        self._pending_replies.clear()
