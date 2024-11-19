from setuptools import setup, find_packages

setup(
    name="git-commit-assistant",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "gitpython>=3.1.41",
        "python-dotenv>=1.0.1",
        "openai>=1.12.0",
        "rich>=13.7.0",
        "click>=8.1.7",
    ],
    entry_points={
        'console_scripts': [
            'gc=main:main',
        ],
    },
) 