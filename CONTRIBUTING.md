# Contributing

Thanks for helping improve DramaFlow QC.

## Development

1. Fork or clone the repository.
2. Create a virtual environment.
3. Install with `pip install -e .`.
4. Run `python -m unittest discover -s tests -v` before opening a PR.

Keep checks small, deterministic, and local-first. A new validator should return structured `CheckResult` values rather than printing directly.

## Pull requests

Please include:

- what production problem the change solves;
- a test covering the new behavior;
- any new configuration keys in the README.
