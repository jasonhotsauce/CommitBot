from typing import Dict, List, Optional
import json
import os
from openai import OpenAI
from anthropic import Anthropic
from rich.console import Console

console = Console()

class GitCommitAgent:
    def __init__(self, model="gpt-4", verbose=False):
        self.model = model
        self.verbose = verbose
        self.conversation_history = []
        
        # Initialize API clients based on model
        if model.startswith('gpt'):
            self.api_type = 'openai'
            self.client = OpenAI()
        elif model.startswith('claude'):
            self.api_type = 'anthropic'
            self.client = Anthropic(api_key=os.getenv('CLAUDE_API_KEY'))
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def get_available_functions(self):
        """Define the functions that the AI can call"""
        return [
            {
                "name": "analyze_changes",
                "description": "Analyze the changes in detail",
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
            },
            {
                "name": "format_commit_message",
                "description": "Format the final commit message following company standards",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Type of change (feat, fix, docs, etc.)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Short description (max 100 chars) for the first line"
                        },
                        "details": {
                            "type": "string",
                            "description": "Detailed description of all changes, including file-by-file breakdown if needed"
                        }
                    },
                    "required": ["type", "description", "details"]
                }
            }
        ]

    def _call_ai_api(self, messages, function_call=None):
        """Make API calls to either OpenAI or Anthropic"""
        if self.api_type == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                functions=self.get_available_functions(),
                function_call=function_call
            )
            if self.verbose:
                console.print(f"[info]Response: {response}[/]")
            
            # Handle OpenAI response structure
            message = response.choices[0].message
            return {
                'content': message.content,
                'function_call': message.function_call
            }
        else:  # anthropic
            # Convert OpenAI-style messages to Anthropic format
            prompt = self._convert_to_anthropic_prompt(messages)
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
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
            elif "format_commit_message" in text:
                # Extract type, description, and details from the formatted message
                lines = text.strip().split('\n')
                first_line = lines[0]
                type_ = first_line.split(':')[0]
                description = first_line.split(':')[1].strip()
                details = '\n'.join(lines[3:]) if len(lines) > 3 else ""
                
                return {
                    'content': text,
                    'function_call': {
                        'name': 'format_commit_message',
                        'arguments': json.dumps({
                            'type': type_,
                            'description': description,
                            'details': details
                        })
                    }
                }
            return {'content': text, 'function_call': None}
        except Exception as e:
            console.print(f"[warning]Error parsing Anthropic response: {str(e)}[/]")
            return {'content': str(content), 'function_call': None}

    def analyze_changes(self, changes: List[Dict]) -> Dict:
        """Analyze the changes in detail"""
        analysis = {
            'file_types': set(),
            'total_additions': 0,
            'total_deletions': 0,
            'changes_by_type': {},
            'major_changes': [],
            'files_changed': []
        }
        
        for change in changes:
            analysis['file_types'].add(change['file_type'])
            analysis['total_additions'] += change['additions']
            analysis['total_deletions'] += change['deletions']
            analysis['files_changed'].append({
                'path': change['path'],
                'change_type': change['change_type'],
                'changes': f"+{change['additions']}, -{change['deletions']}"
            })
            
            if change['change_type'] not in analysis['changes_by_type']:
                analysis['changes_by_type'][change['change_type']] = 0
            analysis['changes_by_type'][change['change_type']] += 1
            
            if change['additions'] + change['deletions'] > 50:
                analysis['major_changes'].append(change['path'])
        
        return analysis

    def decide_next_action(self, changes: List[Dict], untracked: List[str]) -> str:
        """Let AI decide what to do with the changes"""
        if self.verbose:
            console.print("[info]Preparing change summary...[/]")
        
        changes_summary = self._prepare_changes_summary(changes, untracked)
        
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
                
                2. Add exactly TWO blank lines after the first line
                
                3. Detailed description must:
                   - Only describe changes that are actually present in the diff
                   - Start with a clear overview of what the changes accomplish
                   - Include a file-by-file breakdown for multiple file changes
                   - Mention specific functions/features that were modified
                   - Highlight any important technical details from the diff
                   - Use bullet points for multiple changes
                   - Never make assumptions about changes not shown in the diff
                   - Never include speculative or future changes
                
                Examples of good commit messages:

                feat: add git diff analysis functionality to GitAnalyzer class


                Implement detailed git diff analysis in GitAnalyzer:
                - Add get_staged_changes() method to extract diff information
                - Implement diff parsing for additions and deletions count
                - Add file type detection based on file extensions
                - Handle both new and modified files in the diff
                
                Technical details:
                - Use GitPython's diff interface for staged changes
                - Implement proper error handling for binary files
                - Add type hints and documentation

                ---
                fix: resolve crash when analyzing binary files in git diff


                Fix exception handling in GitAnalyzer's diff processing:
                - Add try-catch block around diff.decode() calls
                - Skip binary files with warning message
                - Maintain list of processed files even if some fail
                
                Files modified:
                - git_analyzer.py: Add binary file detection and error handling
                - main.py: Improve error reporting for failed diff analysis"""
            },
            {
                "role": "user",
                "content": f"Analyze these changes and generate a commit message that precisely describes them:\n\n{changes_summary}"
            }
        ]
        
        try:
            response = self._call_ai_api(
                self.conversation_history,
                function_call={"name": "analyze_changes"}
            )
            
            if self.verbose:
                console.print(f"[info]Received response from {self.api_type.upper()}...[/]")
                console.print(f"[info]Response: {response['content']}[/]")
            self.conversation_history.append({
                "role": "assistant",
                "content": response['content'],
                "function_call": response['function_call']
            })
            
            return self._handle_ai_response(response, changes)
            
        except Exception as e:
            console.print(f"[error]Error in AI decision making: {str(e)}[/]")
            return None

    def _prepare_changes_summary(self, changes: List[Dict], untracked: List[str]) -> str:
        """Prepare a detailed summary of changes for AI analysis"""
        summary = "Changes to be committed:\n\n"
        
        for change in changes:
            summary += (
                f"File: {change['path']}\n"
                f"Type: {change['change_type']}\n"
                f"Changes: +{change['additions']}, -{change['deletions']}\n"
                f"File type: {change['file_type']}\n"
                f"Diff:\n{change['diff']}\n\n"
            )
        
        if untracked:
            summary += "\nUntracked files:\n" + "\n".join(untracked)
        
        return summary

    def _handle_ai_response(self, response, changes: List[Dict]) -> Optional[str]:
        """Handle the AI's response and function calls"""
        function_call = response.get('function_call')
        content = response.get('content')

        if not function_call:
            return content
            
        function_name = function_call.name if self.api_type == 'openai' else function_call['name']
        function_args = json.loads(function_call.arguments if self.api_type == 'openai' else function_call['arguments'])
        
        if function_name == "analyze_changes":
            if self.verbose:
                console.print("[info]Running analyze_changes function...[/]")
            analysis = self.analyze_changes(changes)
            return self._continue_conversation(analysis, changes)
        elif function_name == "format_commit_message":
            if self.verbose:
                console.print("[info]Running format_commit_message function...[/]")
            return f"{function_args['type']}: {function_args['description']}\n\n\n{function_args['details']}"
        
        return None

    def _continue_conversation(self, analysis: Dict, changes: List[Dict]) -> str:
        """Continue the conversation with AI using the analysis"""
        self.conversation_history.append({
            "role": "user",
            "content": f"""Based on this analysis:
            
            Files changed: {len(analysis['files_changed'])}
            Total changes: +{analysis['total_additions']}, -{analysis['total_deletions']}
            File types: {', '.join(analysis['file_types'])}
            Change types: {analysis['changes_by_type']}
            Major changes: {', '.join(analysis['major_changes']) if analysis['major_changes'] else 'None'}
            
            Generate a detailed commit message following the required format."""
        })
        
        response = self._call_ai_api(
            self.conversation_history,
            function_call={"name": "format_commit_message"}
        )
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response['content'],
            "function_call": response['function_call']
        })
        
        return self._handle_ai_response(response, changes) 