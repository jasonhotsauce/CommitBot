from typing import Dict, Optional, Tuple, List
import json
import os
from openai import OpenAI
from anthropic import Anthropic
from anthropic.types import Message
from anthropic.types.tool_choice_tool_param import ToolChoiceToolParam
from rich.console import Console
from git_analyzer import GitAnalyzer

console = Console()


class GitCommitAgent:
    """
    AI-powered agent that analyzes Git changes and generates commit messages.
    Supports OpenAI, Anthropic, and local models for generating contextual commit messages.
    """

    def __init__(
        self, git_analyzer: GitAnalyzer, model="gpt-4", local=False, verbose=False
    ):
        self.model = model
        self.verbose = verbose
        self.conversation_history = []
        self.git = git_analyzer
        # Initialize API clients based on model
        if model.startswith("gpt"):
            self.api_type = "openai"
            self.client = OpenAI()
        elif model.startswith("claude"):
            self.api_type = "anthropic"
            self.client = Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))
        elif local:
            self.api_type = "local"
            self.client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
        else:
            raise ValueError(f"Unsupported model: {model}")

    def _get_available_functions(self):
        """Define the functions that the AI can call"""
        analyze_function = {
            "name": "analyze_changes",
            "description": """Analyze staged git changes to determine modifications and their scope.
                    For each changed file, it:
                    1. Gets change type from git status (M=modified, A=added, D=deleted, R=renamed)
                    2. Examines diff content to identify:
                       - Modified lines and functions
                       - Added parameters, methods and features
                       - Config changes and file-level changes
                    3. Provides breakdown of:
                       - Lines added/deleted
                       - Affected file types
                       - Change nature (structural/feature/bugfix)
                    
                    Only analyzes changes shown in git diff without assumptions.""",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "changes": {
                                "type": "array",
                                "description": "List of changes to analyze",
                                "items": {
                                    "type": "object"
                                }
                            }
                        },
                        "required": ["changes"]
                    }
        }
        if self.api_type == "openai" or self.api_type == "local":
            return [
                {
                    "type": "function",
                    "function": analyze_function,
                }
            ]
        else:
            # For Anthropic, convert parameters to input_schema
            analyze_function["input_schema"] = analyze_function.pop("parameters")
            return [analyze_function]

    def _call_ai_api(self, messages, function_call=None):
        """Make API calls to either OpenAI or Anthropic"""
        tools = self._get_available_functions()
        if self.api_type == "openai" or self.api_type == "local":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice=function_call if function_call else "auto",
            )
            if self.verbose:
                console.print(f"[info]Response: {response}[/]")

            # Handle OpenAI response structure
            message = response.choices[0].message
            return message
        else:  # anthropic
            # Convert OpenAI-style messages to Anthropic format
            system_prompt, msgs = self._convert_to_anthropic_prompt(messages)
            print(system_prompt)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                tools=tools,
                tool_choice=function_call,
                system=system_prompt,
                messages=msgs,
            )
            if self.verbose:
                console.print(
                    f"[info]Received response from {self.api_type.upper()}...[/]"
                )
                console.print(f"[info]Response: {response}[/]")
            # Parse Anthropic response to extract function calls
            return response

    def _convert_to_anthropic_prompt(self, messages) -> Tuple[str, List[dict]]:
        """Convert OpenAI-style messages to Anthropic format"""
        system_prompt = ""
        new_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user" or msg["role"] == "assistant":
                new_messages.append(msg)
        return (system_prompt, new_messages)

    def _parse_anthropic_response(self, content):
        """Parse Anthropic response to extract potential function calls"""
        try:
            # Handle content being a list of TextBlocks or a single TextBlock
            if hasattr(content, "text"):
                text = content.text
            elif isinstance(content, list) and hasattr(content[0], "text"):
                text = content[0].text
            else:
                text = str(content)

            # Look for function call patterns in the response
            if "analyze_changes" in text:
                return {
                    "content": text,
                    "function_call": {
                        "name": "analyze_changes",
                        "arguments": '{"changes": []}',
                    },
                }
            return {"content": text, "function_call": None}
        except Exception as e:
            console.print(f"[warning]Error parsing Anthropic response: {str(e)}[/]")
            return {"content": str(content), "function_call": None}

    def analyze_changes(self) -> Dict:
        """Analyze the changes in detail"""
        return self.git.analyze_changes()

    def decide_next_action(self) -> str:
        """Let AI decide what to do with the changes"""
        if self.verbose:
            console.print("[info]Preparing change summary...[/]")

        if self.verbose:
            console.print(f"[info]Sending request to {self.api_type.upper()}...[/]")

        self.conversation_history = [
            {
                "role": "system",
                "content": """You are a Git commit assistant that generates precise commit messages based ONLY on the actual changes provided. Follow these strict rules:

                1. First line format must be: {type}: {short description}
                   - Type MUST be one of: feat, fix, docs, style, refactor, perf, test, build, ci, chore
                   - Description must be under 100 chars and describe the actual change
                   - Never end with a period
                   - Use imperative mood ("add" not "adds" or "added")
                   - For modifications to existing code, use verbs like "update", "modify", "enhance"
                   - Only use "add" when introducing completely new files or features
                
                2. Add exactly TWO blank lines after the first line
                
                3. Detailed description must:
                   - Only describe changes that are actually present in the diff
                   - Pay strict attention to the Change Status of each file:
                     * "Modified existing file" means the file existed before and was changed
                     * "New file" means this is the first commit introducing this file
                   - Start with a clear overview of what the changes accomplish
                   - Include a file-by-file breakdown for multiple file changes
                   - For modified files:
                     * Focus on what was changed in the file
                     * Describe specific modifications made
                     * Don't describe the file as new or added
                   - For new files:
                     * Indicate that they are new additions
                   - Use bullet points for multiple changes
                   - Be precise about what was actually changed
                   - Never make assumptions about changes not shown in the diff
                
                4. Common mistakes to avoid:
                   - Don't say a file was "added" if its Change Status is "Modified existing file"
                   - Don't describe existing features or classes as new
                   - Don't include changes that aren't in the diff
                   - Don't speculate about future changes""",
            },
            {
                "role": "user",
                "content": "Analyze the changes in my repository and generate a commit message that precisely describes them.",
            },
        ]

        try:
            function_call = (
                {
                    "type": "function",
                    "function": {"name": "analyze_changes"},
                }
                if self.api_type == "openai" or self.api_type == "local"
                else ToolChoiceToolParam(name="analyze_changes", type='tool')
            )
            response = self._call_ai_api(
                self.conversation_history,
                function_call=function_call,
            )
            self.conversation_history.append(response)
            return self._handle_ai_response(response)

        except Exception as e:
            console.print(f"[error]Error in AI decision making: {str(e)}[/]")
            return None

    def _handle_ai_response(self, response) -> Optional[str]:
        """Handle the AI's response and function calls"""

        if self.api_type == "openai" or self.api_type == "local":
            tool_calls = response.tool_calls
            if not tool_calls:
                return response.content
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                tool_call_id = tool_call.id
        else:
            is_tool_call = response.stop_reason == 'tool_use'
            if not is_tool_call:
                return response.content
            tool_block = response.content[0]
            function_name = tool_block.name
            tool_call_id = tool_block.id

        if function_name == "analyze_changes":
            if self.verbose:
                console.print("[info]Running analyze_changes function...[/]")
            analysis = self.analyze_changes()
            return self._continue_conversation(analysis, tool_call_id)
        return None

    def _continue_conversation(self, analysis: Dict, tool_call_id: str) -> str:
        """Continue the conversation with AI using the analysis"""
        if self.api_type == "openai" or self.api_type == "local":
            self.conversation_history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(analysis),
                }
            )
        else:
            self.conversation_history.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": json.dumps(analysis)
                        }
                    ]
                }
            )

        response = self._call_ai_api(self.conversation_history)

        self.conversation_history.append(response)

        return self._handle_ai_response(response)





