from __future__ import annotations

from typing import TYPE_CHECKING, Any
from typing_extensions import override

from .._utils import LazyProxy
from .._exceptions import OpenAIError

INSTRUCTIONS = """

You tried to access openai.{symbol}, but this is no longer supported in openai>=1.0.0 - see the README at https://github.com/openai/openai-python for the API.

You can run `openai migrate` to automatically upgrade your codebase to use the 1.0.0 interface. 

Alternatively, you can pin your installation to the old version, e.g. `pip install openai==0.28`

A detailed migration guide is available here: https://github.com/openai/openai-python/discussions/742
"""


class APIRemovedInV1(OpenAIError):
    def __init__(self, *, symbol: str) -> None:
        super().__init__(INSTRUCTIONS.format(symbol=symbol))


class APIRemovedInV1Proxy(LazyProxy[Any]):
    def __init__(self, *, symbol: str) -> None:
        super().__init__()
        self._symbol = symbol

    @override
    def __load__(self) -> Any:
        # return the proxy until it is eventually called so that
        # we don't break people that are just checking the attributes
        # of a module
        return self

    def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
        raise APIRemovedInV1(symbol=self._symbol)


SYMBOLS = [
    "Edit",
    "File",
    "Moderation",
    "ErrorObject",
    "FineTuningJob",
    "ChatCompletion",
]

# we explicitly tell type checkers that nothing is exported
# from this file so that when we re-export the old symbols
# in `openai/__init__.py` they aren't added to the auto-complete
# suggestions given by editors
if TYPE_CHECKING:
    __all__: list[str] = []
else:
    __all__ = SYMBOLS


__locals = locals()
for symbol in SYMBOLS:
    __locals[symbol] = APIRemovedInV1Proxy(symbol=symbol)



"""Demo steps for integration-testing the application stack."""

from ..base_step import BaseStep
from ...components import R


@R.register("demo_echo_step1")
class DemoEchoStep1(BaseStep):
    """Read query/min_score from context, normalize, and write back for Step2."""

    async def execute(self):
        assert self.context is not None
        query = self.context.get("query", "")
        self.context["processed_query"] = processed_query
        self.context["adjusted_min_score"] = adjusted_min_score

        return self.context.response


@R.register("demo_echo_step2")
class DemoEchoStep2(BaseStep):
    """Consume Step1's outputs from context and emit the final response."""

    async def execute(self):
        assert self.context is not None
        query = self.context.get("query", "")
        min_score = self.context.get("min_score", 0.5)
        processed_query = self.context.get("processed_query", "")
        adjusted_min_score = self.context.get("adjusted_min_score", min_score)

        self.logger.info(
            f"[{self.name}] query={query!r}, min_score={min_score}, "
            f"processed_query={processed_query!r}, adjusted_min_score={adjusted_min_score}",
        )

        self.context.response.answer = f"echo: {processed_query} (min_score={adjusted_min_score})"
        self.context.response.metadata.update(
            {
                "step": self.name,
                "adjusted_min_score": adjusted_min_score,
            },
        )
        return self.context.response



# Copyright (c) 2023 - 2025, AG2ai, Inc., AG2ai open-source projects maintainers and core contributors
#
# SPDX-License-Identifier: Apache-2.0
#
__all__: list[str] = []

from .available_condition import ExpressionAvailableCondition, StringAvailableCondition
from .context_condition import ExpressionContextCondition, StringContextCondition
from .context_expression import ContextExpression
from .context_str import ContextStr
from .context_variables import ContextVariables
from .targets.group_chat_target import GroupChatConfig, GroupChatTarget

"""
from .targets.group_manager_target import (
    GroupManagerSelectionMessageContextStr,
    GroupManagerSelectionMessageString,
    GroupManagerTarget,
)
"""
from .targets.transition_target import (
    AgentNameTarget,
    AgentTarget,
    StayTarget,
    TerminateTarget,
)

__all__ = [
    "AgentNameTarget",
    "AgentTarget",
    "ContextStr",
    "GroupChatTarget",
    # "GroupManagerSelectionMessageContextStr",
    # "GroupManagerSelectionMessageString",
    # "GroupManagerTarget",
    "Handoffs",
    "NestedChatTarget",
    "OnCondition",
    "StringLLMCondition",
    "TerminateTarget",
]


# ============================================================================
# СИНТЕТИКА (дописано для покрытия top-level кейсов «.»-стратегии).
# Ниже — намеренно расставленные конструкции, которых не было в собранных
# кусках выше; код нерабочий, важна форма.
# ============================================================================

# --- 1. однострочные простые константы: declared surface, тела нет ---
MAX_RETRIES = 3
TIMEOUT_SECONDS: float = 30.0          # аннотированная
DEFAULT_ENCODING = "utf-8"
_PRIVATE_FLAG = False                  # приватная (ведущее подчёркивание)

# --- 2. многострочный SCREAMING_CASE dict — главный foldable-кейс ---
# (ведущий doc-коммент над константой: должен ли приклеиться, как у def?)
DEFAULT_CONFIG = {
    "retries": MAX_RETRIES,
    "timeout": TIMEOUT_SECONDS,
    "nested": {                        # вложенный dict — тут вопрос "нырять ладдером или лист"
        "backoff": "exponential",
        "jitter": True,
    },
}

# --- 3. многострочный кортеж-константа с аннотацией ---
SUPPORTED_VERSIONS: tuple[str, ...] = (
    "1.0.0",
    "1.1.0",
    "2.0.0",
)

# --- 4. однострочный dict (НЕ блок: сворачивать нечего) ---
FLAGS = {"debug": False, "verbose": True}

# --- 5. константы ВНУТРИ класса: уровень должен быть = соседний метод, не файловый ---
class Settings:
    """Класс с class-level константами (проверка уровня относительно методов)."""

    RETRY_LIMIT = 5                    # однострочная class-level константа
    HEADERS = {                        # многострочная class-level dict-константа
        "Accept": "application/json",
        "User-Agent": "edge/1.0",
    }

    def load(self) -> dict:            # метод-сосед: с ним сверяем уровень HEADERS
        return dict(self.HEADERS)

