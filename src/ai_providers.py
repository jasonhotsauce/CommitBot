"""Module for interacting with different AI providers"""

from abc import ABC, abstractmethod
from typing import Optional, Sequence, Union, Callable
from ollama import Message, Tool, Client as OllamaClient

class AIProvider(ABC):
    """Abstract base class for AI providers"""

    @abstractmethod
    def __init__(self, model: str):
        pass

    @abstractmethod
    def complete(self, message: Message, tools: Optional[Sequence[Union[Tool, Callable]]] = None) -> str:
        """Calling the LLM model to complete a message"""
        pass

class OllamaProvider(AIProvider):
    """Provider for Ollama"""

    def __init__(self, model: str):
        self.model = model
        self.client = OllamaClient()

    def complete(self, 
                 message: Optional[Sequence[Message]] = None, 
                 tools: Optional[Sequence[Union[Tool, Callable]]] = None) -> str:
        """Calling the LLM model to complete a message"""
        return self.client.chat(model=self.model, messages=message, tools=tools)

class OpenAIProvider(AIProvider):
    """Provider for OpenAI"""

    def __init__(self, model: str):
        self.model = model

class AnthropicProvider(AIProvider):
    """Provider for Anthropic"""

    def __init__(self, model: str):
        self.model = model
