"""A FastAPI server that acts as a TwiML voice agent"""
__version__ = "0.1.21"
__all__ = [
    "AbstractConvoManager",
    "Server",
    "ConversationRelayServer",
    "VirtualAgent",
    "LLMAgent",
    "SquareSchedulingAgent",
    "SquareClient",
    "Talker",
    "TalkerConfig"
    "TalkerReasonerConvoManager",
]

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .basic_server import Server
    from .abstract_convo_manager import AbstractConvoManager
    from .cr_server import ConversationRelayServer
    from .agent import VirtualAgent
    from .llm_agent import LLMAgent
    from .square_scheduling_agent import SquareSchedulingAgent
    from .square_client import SquareClient
    from .talker import Talker
    from .talker_reasoner_convo_manager import TalkerConfig, TalkerReasonerConvoManager
else:
    def __getattr__(name):
        """
        Loads some exported package attributes lazily.
        """

        if name == "Server":
            from .basic_server import Server
            return Server

        if name == "ConversationRelayServer":
            from .cr_server import ConversationRelayServer
            return ConversationRelayServer

        if name == "VirtualAgent":
            from .agent import VirtualAgent
            return VirtualAgent

        if name == "LLMAgent":
            from .llm_agent import LLMAgent
            return LLMAgent

        if name == "SquareSchedulingAgent":
            from .square_scheduling_agent import SquareSchedulingAgent
            return SquareSchedulingAgent

        if name == "SquareClient":
            from .square_client import SquareClient
            return SquareClient

        if name == "Talker":
            from .talker import Talker
            return Talker

        if name == "AbstractConvoManager":
            from .abstract_convo_manager import AbstractConvoManager
            return AbstractConvoManager

        if name == "TalkerConfig":
            from .talker_reasoner_convo_manager import TalkerConfig
            return TalkerConfig

        if name == "TalkerReasonerConvoManager":
            from .talker_reasoner_convo_manager import TalkerReasonerConvoManager
            return TalkerReasonerConvoManager

        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
