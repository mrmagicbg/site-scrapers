# Contributing Guide

Thank you for your interest in contributing to the site-scrapers project!

## Development Setup

### Prerequisites
- Python 3.8+ 
- Git

### Quick Setup
```bash
git clone https://github.com/ivan-madjarov/site-scrapers.git
cd site-scrapers
make setup-venv           # Create virtual environment
make install-dev          # Install all dependencies including Playwright  
make test                 # Run tests to verify setup
```

### Development Workflow

1. **Create a branch** for your feature/fix
2. **Make changes** following the code style
3. **Test thoroughly** using:
   ```bash
   make test            # Run pytest suite
   make test-scraper    # Test core scraper
   make validate        # Run comprehensive validation
   ```
4. **Update documentation** as needed
5. **Submit a pull request**

## Code Style

### Python Standards
- Follow PEP 8 conventions
- Use meaningful variable/function names
- Add docstrings for public functions
- Keep functions focused and testable

### Editor Configuration
This repository intentionally keeps editor configuration out of version control (see `.gitignore` for `.vscode/`).

**Recommended VS Code Extensions:**
- `ms-python.python` (Python support)
- `ms-python.vscode-pylance` (type checking and completion)  
- `ms-python.black-formatter` (code formatting)

**Optional `.vscode/settings.json` (create locally):**
```json
{
  "python.languageServer": "Pylance",
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

## Testing

### Test Categories
- **Unit Tests**: `pytest ebag_product_scraper/tests/`
- **Integration Tests**: `make test-scraper`
- **Validation Tests**: `make validate` (tests 98%+ extraction rates)

### Adding Tests
When adding new features:
1. Add unit tests in `ebag_product_scraper/tests/`
2. Update validation script if needed
3. Ensure all extraction rates remain high

## Project Structure

```
site-scrapers/
├── ebag_product_scraper/     # Core scraper package
│   ├── scraper.py           # Main extraction logic
│   └── tests/               # Unit tests
├── tools/                   # Utilities
├── ebag_runner.py          # CLI runner
├── validate_solution.sh    # Validation script
└── categories.txt          # Full category list
```

## Contribution Guidelines

### Bug Reports
- Use GitHub issues
- Include error messages and steps to reproduce
- Mention your Python version and OS

### Feature Requests
- Describe the use case clearly
- Consider backward compatibility
- Discuss performance implications

### Pull Requests
- Reference related issues
- Include tests for new functionality
- Update documentation
- Maintain the 98%+ quantity extraction rate

## Performance Expectations

This project maintains **98%+ quantity extraction rates** across diverse Bulgarian e-commerce categories. Any changes should preserve or improve this performance standard.

## Questions?

Feel free to open an issue for questions or join discussions in existing issues!