"""Module for a facade to different AI providers"""

from typing import Tuple, Optional, List
from openai import OpenAI
from anthropic import Anthropic
from ollama import Client as OllamaClient
from ollama import Message, Tool

SUPPORTED_PROVIDERS = ['openai', 'anthropic', 'ollama']

class AIClient:
    """Facade for different AI providers"""

    def __init__(self, model: str, api_key: str):
        self.provider, self.model_name = self._validate_model(model)
        self._ai_provider = self._initialize_provider(api_key)

    @classmethod
    def _validate_model(cls, model: str) -> Tuple[str, str]:
        provider, model_name = model.split(':')
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}. Supported providers: {SUPPORTED_PROVIDERS}")
        return provider, model_name
    
    def _initialize_provider(self, api_key: str):
        if self.provider == 'openai':
            return OpenAI(api_key=api_key)
        elif self.provider == 'anthropic':
            return Anthropic(api_key=api_key)
        elif self.provider == 'ollama':
            return OllamaClient(api_key=api_key)
        
    def create(self, message: Message, tools: Optional[List[Tool]]):
        pass
    