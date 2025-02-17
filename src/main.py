"""
Command-line interface for AI-powered Git commit message generation.
Analyzes staged changes and suggests meaningful commit messages using OpenAI's API.
"""

import os
import sys
import traceback
import click
from dotenv import load_dotenv, set_key
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.prompt import Confirm
from git.exc import GitCommandError
from openai import APIError

from git_analyzer import GitAnalyzer
from git_commit_agent import GitCommitAgent

# Define custom theme
custom_theme = Theme({
    'info': 'cyan',
    'warning': 'yellow',
    'error': 'bold red',
    'success': 'bold green',
    'file': 'blue',
    'change_type': 'magenta',
    'diff_add': 'green',
    'diff_remove': 'red',
    'commit_msg': 'bold cyan',
    'header': 'bold blue'
})

console = Console(theme=custom_theme)

def setup_api_key(model: str):
    """Setup API key if not present"""
    key_name = 'OPENAI_API_KEY' if model.startswith('gpt') else 'CLAUDE_API_KEY'
    api_key = os.getenv(key_name)
    
    if not api_key:
        console.print(f"[warning]No {key_name} found in environment[/]")
        api_key = click.prompt("Please enter your API key", hide_input=True)
        
        # Save to .env file
        env_file = os.path.join(os.getcwd(), '.env')
        set_key(env_file, key_name, api_key)
        console.print("[success]API key saved to .env file[/]")
        os.environ[key_name] = api_key
    return api_key

@click.command()
@click.option('--dry-run', is_flag=True, help='Show suggested message without committing')
@click.option('--model', 
              default='gpt-4',
              help='AI model to use (e.g., gpt-4, gpt-3.5-turbo, claude-3-opus, claude-3-sonnet, or local model name)')
@click.option('--local', is_flag=True, default=False, help='Use local model')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed analysis')
def main(dry_run: bool, model: str, local: bool, verbose: bool):
    """AI-powered Git commit message generator"""
    try:
        load_dotenv()
        
        if not local and (model.startswith('gpt') or model.startswith('claude')):
            api_key = setup_api_key(model)
            if not api_key:
                console.print("[error]Failed to setup API key[/]")
                sys.exit(1)
        
        git = GitAnalyzer(verbose=verbose)
        git.analyze_changes()
        agent = GitCommitAgent(git_analyzer=git, model=model, local=local, verbose=verbose)

        staged_changes = git.get_staged_changes()
        if not staged_changes:
            console.print("[warning]No staged changes found. Stage your changes first with 'git add'[/]")
            sys.exit(1)

        console.print("[info]AI agent is analyzing changes...[/]")
        commit_message = agent.decide_next_action()

        if commit_message:
            console.print("\n[header]AI suggested commit message:[/]")
            console.print(Panel(commit_message, style="commit_msg", expand=False))

            if not dry_run and Confirm.ask("\nProceed with this commit message?"):
                if git.commit_changes(commit_message):
                    console.print("[success]Changes committed successfully![/]")
                else:
                    console.print("[error]Failed to commit changes[/]")

    except (GitCommandError, EnvironmentError, APIError) as e:
        console.print(f"[error]An error occurred: {str(e)}[/]")
        console.print(f"[error]Stacktrace:\n{traceback.format_exc()}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main()
