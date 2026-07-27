# Contributing

Thanks for helping improve this project.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev,web]'
```

## Before submitting a pull request

- Run the test suite
- Run formatting checks if you changed Python code
- Keep changes focused and explain the reason in the PR description

```bash
pytest
black --check src tests
isort --check src tests
```

## Pull request expectations

- Describe the problem and solution clearly
- Mention any related issues
- Keep the scope limited to the feature or fix
