"""Module for analyzing Git repositories and their changes, providing detailed insights about staged files and commits."""

from typing import Dict, List
from git import Repo
from rich.console import Console

console = Console()

class GitAnalyzer:
    """Class for analyzing Git repositories and their changes"""
    def __init__(self, repo_path='.', verbose=False):
        self.repo = Repo(repo_path)
        self.verbose = verbose
  
    def get_staged_changes(self) -> List[Dict]:
        """Get detailed information about staged changes"""
        changes = []
     
        try:
            # For repositories with commits
            staged_diff = self.repo.index.diff("HEAD")
            # Process normal staged changes
            for diff in staged_diff:
                try:
                    # Get the raw diff text
                    diff_text = self.repo.git.diff('--cached', diff.a_path)
                  
                    # Determine change type
                    change_type = 'M'  # Default to modified
                    if diff.new_file:
                        change_type = 'A'
                    elif diff.deleted_file:
                        change_type = 'D'
                    elif diff.renamed:
                        change_type = 'R'
                  
                    change_info = {
                        'path': diff.a_path,
                        'change_type': change_type,
                        'additions': diff_text.count('\n+'),
                        'deletions': diff_text.count('\n-'),
                        'diff': diff_text,
                        'file_type': diff.a_path.split('.')[-1] if '.' in diff.a_path else 'unknown'
                    }
                    changes.append(change_info)
                except Exception as e:
                    console.print(f"[warning]Could not process file {diff.a_path}: {str(e)}[/]")

        except Exception as e:
            # For newly initialized repositories
            console.print("[info]Processing new repository...[/]")

            # Get all staged files (works for both new and existing repos)
            staged_files = self.repo.git.diff('--cached', '--name-only').split('\n')
            staged_files = [f for f in staged_files if f]  # Remove empty strings

            for staged_file in staged_files:
                try:
                    # Get the diff for the staged file
                    diff_text = self.repo.git.diff('--cached', staged_file)

                    # For new repositories, check if file exists in HEAD
                    try:
                        self.repo.head.commit.tree[staged_file]
                        change_type = 'M'  # File exists in HEAD, so it's modified
                    except (KeyError, ValueError):
                        change_type = 'A'  # File doesn't exist in HEAD, so it's new

                    change_info = {
                        'path': staged_file,
                        'change_type': change_type,
                        'additions': diff_text.count('\n+'),
                        'deletions': diff_text.count('\n-'),
                        'diff': diff_text,
                        'file_type': staged_file.split('.')[-1] if '.' in staged_file else 'unknown'
                    }
                    changes.append(change_info)
                except Exception as e:
                    console.print(f"[warning]Could not process file {staged_file}: {str(e)}[/]")

        return changes

    def get_untracked_files(self) -> List[str]:
        """Get list of untracked files"""
        return self.repo.untracked_files
    
    def analyze_changes(self) -> Dict:
        """Analyze the changes in detail"""
        # Get the raw changes instead of the formatted summary
        changes = self.get_staged_changes()  # This returns List[Dict]
        
        analysis = {
            'file_types': set(),
            'total_additions': 0,
            'total_deletions': 0,
            'changes_by_type': {},
            'major_changes': [],
            'files_changed': [],
            'summary': self._prepare_changes_summary()
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
        
        # Convert set to list for JSON serialization
        analysis['file_types'] = list(analysis['file_types'])
        return analysis
    
    def commit_changes(self, message: str) -> bool:
        """Commit staged changes with the given message"""
        try:
            # Create an initial commit if this is a new repository
            if not self.repo.head.is_valid():
                console.print("[info]Creating initial commit...[/]")
            
            self.repo.index.commit(message)
            return True
        except Exception as e:
            console.print(f"[error]Failed to commit changes: {str(e)}[/]")
            return False
        
    def _prepare_changes_summary(self) -> str:
        """Prepare a detailed summary of changes for AI analysis"""
        staged_changes = self.get_staged_changes()
        untracked_files = self.get_untracked_files()
        
        summary = "Changes to be committed:\n\n"
        
        for change in staged_changes:
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
        
        if untracked_files:
            summary += "\nUntracked files:\n" + "\n".join(untracked_files)
        
        return summary