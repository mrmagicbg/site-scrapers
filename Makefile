PYTHON ?= python3
PIP ?= $(PYTHON) -m pip
VENV_PATH ?= .venv

# Setup and installation
install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install playwright pytest
	$(PYTHON) -m playwright install chromium

setup-venv:
	$(PYTHON) -m venv $(VENV_PATH)
	$(VENV_PATH)/bin/pip install --upgrade pip
	$(VENV_PATH)/bin/pip install -r requirements.txt

# Testing and validation
test:
	pytest -q

test-scraper:
	$(PYTHON) ebag_product_scraper/scraper.py --file ebag_product_scraper/sample_product.html

validate:
	./validate_solution.sh

# Example runs
demo-single:
	$(PYTHON) ebag_runner.py --category "https://www.ebag.bg/categories/plodove/600"

demo-full:
	$(PYTHON) ebag_runner.py --categories-file categories.txt

# Maintenance
clean:
	-find . -name "__pycache__" -type d -exec rm -rf {} +
	-find . -name "*.pyc" -type f -delete

clean-exports:
	-rm -rf exports/categories_*

clean-artifacts:
	@echo "Removing generated artifacts..."
	-rm -rf .venv images images* *.jsonl printable*.html .playwright .pytest_cache
	-find . -name "*.pyc" -type f -delete
	-find . -name "*.tmp" -type f -delete
	@echo "Done."

# Help
help:
	@echo "Available targets:"
	@echo "  install      - Install Python dependencies"
	@echo "  install-dev  - Install development dependencies (includes Playwright)"
	@echo "  setup-venv   - Create virtual environment and install dependencies"
	@echo "  test         - Run pytest tests"
	@echo "  test-scraper - Test scraper with sample file"
	@echo "  validate     - Run comprehensive validation script"
	@echo "  demo-single  - Run single category demo"
	@echo "  demo-full    - Run full export demo"
	@echo "  clean        - Remove Python cache files"
	@echo "  clean-exports- Remove export directories"
	@echo "  clean-artifacts - Deep clean (removes venv, exports, etc.)"
	@echo "  help         - Show this help message"

.PHONY: install install-dev setup-venv test test-scraper validate demo-single demo-full clean clean-exports clean-artifacts help
