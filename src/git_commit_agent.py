from typing import Dict, List, Optional
import json
import os
from openai import OpenAI
from anthropic import Anthropic
from rich.console import Console

console = Console()

class GitCommitAgent:
    def __init__(self, model="gpt-4", local=False, verbose=False):
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
        elif local:
            self.api_type = 'local'
            self.client = OpenAI(base_url = 'http://localhost:11434/v1',api_key="ollama")
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def get_available_functions(self):
        """Define the functions that the AI can call"""
        return [
            {
                "name": "analyze_changes",
                "description": """Analyze the staged changes in detail. For each file:
                1. Check the Change Status:
                   - 'Modified existing file' means changes to an existing file
                   - 'New file' means a newly created file
                2. Look at the actual diff content to identify:
                   - What specific lines or functions were modified
                   - What new parameters or features were added
                   - What configurations or options were changed
                3. Focus on the actual changes shown in the diff, not the entire file content""",
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
                "description": """Format a commit message that precisely describes the actual changes.
                Rules for different change types:
                - For modified files: Use verbs like 'update', 'add support for', 'enhance'
                - For new files: Use 'add' or 'create'
                - For new features in existing files: Use 'add [feature] to [existing component]'
                
                Message structure:
                1. First line: {type}: {what changed and why, max 100 chars}
                2. Two blank lines
                3. Detailed description:
                   - Start with what the changes accomplish
                   - List specific modifications per file
                   - Include technical details from the diff
                   - Use bullet points for clarity""",
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
            change_type_desc = {
                'M': 'Modified existing file',
                'A': 'New file',
                'D': 'Deleted file',
                'R': 'Renamed file',
                'T': 'Type changed'
            }.get(change['change_type'], change['change_type'])
            
            summary += (
                f"File: {change['path']}\n"
                f"Change Status: {change_type_desc}\n"
                f"Changes: +{change['additions']}, -{change['deletions']}\n"
                f"File type: {change['file_type']}\n"
                f"Change description: Changes to this file include modifications to "
                f"add or update functionality as shown in the diff below.\n"
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
            self.conversation_history,
            function_call={"name": "format_commit_message"}
        )
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response['content'],
            "function_call": response['function_call']
        })
        
        return self._handle_ai_response(response, changes) 