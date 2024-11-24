from typing import Dict, List, Optional
import json
import os
from openai import OpenAI
from anthropic import Anthropic
from rich.console import Console
from git_analyzer import GitAnalyzer

console = Console()

class GitCommitAgent:
    def __init__(self, git_analyzer: GitAnalyzer, model="gpt-4", local=False, verbose=False):
        self.model = model
        self.verbose = verbose
        self.conversation_history = []
        self.git = git_analyzer
        # Initialize API clients based on model
        if model.startswith('gpt'):
            self.api_type = 'openai'
            self.client = OpenAI()
        elif model.startswith('claude'):
            self.api_type = 'anthropic'
            self.client = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        elif local:
            self.api_type = 'local'
            self.client = OpenAI(base_url = 'http://localhost:11434/v1',api_key="ollama")
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _get_available_functions(self):
        """Define the functions that the AI can call"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "analyze_changes",
                    "description": """Analyzes staged git changes to determine modifications and their scope.
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
            },
        ]

    def _call_ai_api(self, messages, function_call=None):
        """Make API calls to either OpenAI or Anthropic"""
        if self.api_type == 'openai' or self.api_type == 'local':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._get_available_functions(),
                tool_choice=function_call if function_call else "auto"
            )
            if self.verbose:
                console.print(f"[info]Response: {response}[/]")
            
            # Handle OpenAI response structure
            message = response.choices[0].message
            return message
        else:  # anthropic
            # Convert OpenAI-style messages to Anthropic format
            prompt = self._convert_to_anthropic_prompt(messages)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                tools=function_call,
                messages=[{"role": "user", "content": prompt}]
            )
            if self.verbose:
                console.print(f"[info]Response: {response}[/]")
            # Parse Anthropic response to extract function calls
            return self._parse_anthropic_response(response.content)

    def _convert_to_anthropic_prompt(self, messages):
        """Convert OpenAI-style messages to Anthropic format"""
        prompt = ""
        for msg in messages:
            if msg['role'] == 'system':
                prompt += f"System: {msg['content']}\n\n"
            elif msg['role'] == 'user':
                prompt += f"Human: {msg['content']}\n\n"
            elif msg['role'] == 'assistant':
                prompt += f"Assistant: {msg['content']}\n\n"
        return prompt.strip()

    def _parse_anthropic_response(self, content):
        """Parse Anthropic response to extract potential function calls"""
        try:
            # Handle content being a list of TextBlocks or a single TextBlock
            if hasattr(content, 'text'):
                text = content.text
            elif isinstance(content, list) and hasattr(content[0], 'text'):
                text = content[0].text
            else:
                text = str(content)
                
            # Look for function call patterns in the response
            if "analyze_changes" in text:
                return {
                    'content': text,
                    'function_call': {
                        'name': 'analyze_changes',
                        'arguments': '{"changes": []}'
                    }
                }
            return {'content': text, 'function_call': None}
        except Exception as e:
            console.print(f"[warning]Error parsing Anthropic response: {str(e)}[/]")
            return {'content': str(content), 'function_call': None}

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
                   - Don't speculate about future changes"""
            },
            {
                "role": "user",
                "content": f"Analyze the changes in my repository and generate a commit message that precisely describes them."
            }
        ]
        
        try:
            response = self._call_ai_api(
                self.conversation_history,
                function_call={"type": "function", "function": {"name": "analyze_changes"}}
            )
            
            if self.verbose:
                console.print(f"[info]Received response from {self.api_type.upper()}...[/]")
                console.print(f"[info]Response: {response.content}[/]")
            self.conversation_history.append(response)
            
            return self._handle_ai_response(response)
            
        except Exception as e:
            console.print(f"[error]Error in AI decision making: {str(e)}[/]")
            return None

    def _handle_ai_response(self, response) -> Optional[str]:
        """Handle the AI's response and function calls"""

        if self.api_type == 'openai' or self.api_type == 'local':
            tool_calls = response.tool_calls
            if not tool_calls:
                return response.content
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                tool_call_id = tool_call.id
                function_args = json.loads(tool_call.function.arguments)
        else:
            tool_calls = response.get('tool_calls')
            if not tool_calls:
                return response.get('content')
            function_name = tool_calls[0].name
            tool_call_id = tool_calls[0].id
            function_args = json.loads(tool_calls[0].arguments)
            
        if function_name == "analyze_changes":
            if self.verbose:
                console.print("[info]Running analyze_changes function...[/]")
            analysis = self.analyze_changes()
            return self._continue_conversation(analysis, tool_call_id)
        return None

    def _continue_conversation(self, analysis: Dict, tool_call_id: str) -> str:
        """Continue the conversation with AI using the analysis"""
        if self.api_type == 'openai' or self.api_type == 'local':
            self.conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(analysis)
            })
        else:
            self.conversation_history.append({
                "role": "user",
            "content": f"""Based on this analysis of the changes:
            
            Files modified: {len(analysis['files_changed'])}
            Total changes: +{analysis['total_additions']}, -{analysis['total_deletions']}
            File types: {', '.join(analysis['file_types'])}
            Change types: {analysis['changes_by_type']}
            Major changes: {', '.join(analysis['major_changes']) if analysis['major_changes'] else 'None'}
            
            Remember:
            1. These files are MODIFIED, not new
            2. Focus on what specifically changed in each file
            3. Describe the actual modifications shown in the diff
            4. Don't describe files or classes as new unless marked as 'New file'
            
            Generate a detailed commit message following the required format."""
        })
        
        response = self._call_ai_api(
            self.conversation_history
        )
        
        self.conversation_history.append(response)
        
        return self._handle_ai_response(response) 