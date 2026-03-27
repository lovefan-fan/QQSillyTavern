from __future__ import annotations

import inspect

from langbot_plugin.api.definition.components.common.event_listener import EventListener

from pkg.plugin.context import EventContext as LegacyEventContext


class DefaultEventListener(EventListener):
    async def initialize(self):
        await super().initialize()

        for _, method in inspect.getmembers(self.plugin, predicate=callable):
            func = getattr(method, "__func__", method)
            event_type = getattr(func, "_legacy_event_type", None)
            if event_type is None:
                continue

            @self.handler(event_type)
            async def _dispatch(event_context, legacy_method=method):
                legacy_context = LegacyEventContext.from_sdk(
                    event_context=event_context,
                    plugin=self.plugin,
                )
                await legacy_method(legacy_context)
                await legacy_context.flush()
