from __future__ import annotations

import inspect
import logging

from langbot_plugin.api.definition.components.common.event_listener import EventListener

from pkg.plugin.context import EventContext as LegacyEventContext


logger = logging.getLogger("QQSillyTavern")


class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()

        for _, method in inspect.getmembers(self.plugin, predicate=callable):
            func = getattr(method, "__func__", method)
            event_type = getattr(func, "_legacy_event_type", None)
            if event_type is None:
                continue

            @self.handler(event_type)
            async def _dispatch(event_context, legacy_method=method, legacy_event_type=event_type):
                event_name = getattr(event_context.event, "event_name", None)
                if not event_name:
                    event_name = getattr(legacy_event_type, "__name__", str(legacy_event_type))
                logger.info(
                    "[QQSillyTavern] dispatch event=%s registered_type=%s handler=%s",
                    event_name,
                    getattr(legacy_event_type, "__name__", str(legacy_event_type)),
                    getattr(legacy_method, "__name__", repr(legacy_method)),
                )
                legacy_context = LegacyEventContext.from_sdk(
                    event_context=event_context,
                    plugin=self.plugin,
                )
                await legacy_method(legacy_context)
                await legacy_context.flush()
