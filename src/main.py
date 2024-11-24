import os
import sys
import click
from dotenv import load_dotenv
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.prompt import Confirm

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

@click.command()
@click.option('--dry-run', is_flag=True, help='Show suggested message without committing')
@click.option('--model', default='gpt-4o-mini', help='OpenAI model to use')
@click.option('--local', is_flag=True, default=False, help='Use local model')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed analysis')
def main(dry_run: bool, model: str, local: bool, verbose: bool):
    """AI-powered Git commit message generator"""
    try:
        load_dotenv()
        if not os.getenv('OPENAI_API_KEY'):
            console.print("[error]OPENAI_API_KEY not found in environment variables[/]")
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
        
    except Exception as e:
        import traceback
        console.print(f"[error]An error occurred: {str(e)}[/]")
        console.print(f"[error]Stacktrace:\n{traceback.format_exc()}[/]")
        sys.exit(1)

if __name__ == "__main__":
    main() 