# Git Commit Assistant

Git Commit Assistant is an AI-powered command-line tool that generates meaningful and precise Git commit messages based on the actual changes in your repository. It leverages advanced AI models such as OpenAI's GPT-4, GPT-3.5-turbo, Anthropic's Claude, as well as local model setups to streamline your development workflow.

## Features

- **AI-Driven Commit Messages:** Automatically generates commit messages that accurately describe your changes.
- **Multi-Provider Support:** Works with various AI models/providers (OpenAI, Anthropic, or a local model).
- **Detailed Analysis:** Examines Git diffs to provide a comprehensive breakdown of modifications.
- **Easy Integration:** Simply stage your changes and run the tool to receive AI-generated suggestions.
- **Customizable CLI Options:** Offers options for dry runs, verbose output, and model selection.

## Installation

### Prerequisites

- Python 3.8+
- Git

### Clone the Repository

```bash
git clone https://github.com/yourusername/git-commit-assistant.git
cd git-commit-assistant
```

### Set Up a Virtual Environment (Optional)

It is recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

Install the required dependencies using pip:

```bash
pip install -r requirements.txt
```

Alternatively, install the package using the setup script:

```bash
python setup.py install
```

This will also set up the command-line entry point `commit-assistant`.

## Usage

After installation, you can run the assistant directly from your terminal:

```bash
commit-assistant
```

### Command-Line Options

- `--dry-run`: Displays the suggested commit message without committing your changes.
- `--model`: Select the AI model to use. Examples include:
  - `gpt-4`
  - `gpt-3.5-turbo`
  - `claude-3-opus`
  - `claude-3-sonnet`
  - Or another local model name.
- `--local`: Use a local model instead of a cloud-based API.
- `--verbose` or `-v`: Enables detailed output for troubleshooting or insight into the analysis process.

Example command:

```bash
commit-assistant --dry-run --model gpt-4 --verbose
```

## API Key Setup

The tool requires API keys to interact with external AI providers:

- For OpenAI-based models, set the `OPENAI_API_KEY`.
- For Anthropic models, set the `CLAUDE_API_KEY`.

If an API key is not found in the environment, the tool will prompt you to enter one and will save it to a `.env` file in your project directory. Make sure you have your API keys ready, especially if you are not using local models.

## How It Works

1. **Analyze Changes:** The tool inspects your staged changes using Git diffs, generating a detailed summary of modifications.
2. **Generate Commit Message:** The AI agent uses this analysis to craft a commit message adhering to best practices, including:
   - A concise first line with a specific format.
   - A detailed description (when necessary) outlining file-by-file changes.
3. **Commit (Optional):** Review the AI-generated message and commit the changes with a single confirmation.

## Contributing

Contributions are welcome and appreciated! To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bug fix.
3. Commit your changes with clear and descriptive messages.
4. Open a pull request explaining your modifications.

Feel free to open issues to report bugs or suggest features.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [GitPython](https://gitpython.readthedocs.io/en/stable/)
- [OpenAI API](https://platform.openai.com/)
- [Anthropic](https://www.anthropic.com/)
- [Rich](https://github.com/Textualize/rich)
- [Click](https://click.palletsprojects.com/)

## Contact

For questions or feedback, please open an issue in the repository.

Happy committing with AI assistance!