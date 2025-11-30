# Changelog

All notable changes to this project are documented in this file.

## [2.1.0] - 2025-09-29 - Dual Export Formats & Compact Table Layout

### New Features
- **Dual Export Formats**: Added table format alongside traditional cards layout
- **Compact Table Layout**: 10-column table design optimized for printer scaling
- **Landscape A4 Support**: Table format uses landscape orientation for maximum density
- **Complete Data Preservation**: All product information (names, prices, quantities, codes) maintained in both formats

### CLI Enhancements
- **--html-format parameter**: Choose between 'cards' (default) or 'table' in ebag_runner.py
- **--table-format flag**: Added to full_export.sh for convenient batch table generation
- **--format parameter**: Added to generate_printable.py for standalone format selection

### Technical Improvements
- **Enhanced generate_printable.py**: Refactored with format-specific rendering functions
- **Category Organization**: Table format groups products by category with clear headers
- **Print Optimization**: Table format uses smaller fonts and compact spacing for maximum content
- **CSS Media Queries**: Print-specific styling for both formats

### Integration
- **Full Export Script**: Updated full_export.sh to support table format option
- **Backward Compatibility**: Default cards format preserved, new table format is opt-in
- **Documentation**: Updated README and tools documentation with format examples

## [2.0.1] - 2025-09-28 - Documentation & Project Optimization

### Project Organization
- **Enhanced Makefile**: Added comprehensive targets for setup, testing, validation, and demos
- **Improved Documentation**: Updated all README files with current capabilities and performance metrics
- **Contributing Guide**: Complete development workflow and coding standards documentation
- **Project Metadata**: Updated pyproject.toml to version 2.0.0 with proper dependencies

### Development Tools
- **CI/CD Pipeline**: GitHub Actions workflow for automated testing across Python 3.10-3.12
- **Validation Scripts**: Comprehensive testing demonstrating 98%+ extraction consistency
- **Export Management**: Tools for reprocessing and maintaining export quality
- **Build System**: Make targets for consistent development experience

### File Structure Optimization
- **Cleaned Dependencies**: Streamlined requirements with optional Playwright integration
- **Organized Utilities**: Structured tools directory with clear purposes
- **Proper Gitignore**: Updated exclusions for logs, artifacts, and development files

## [2.0.0] - 2025-09-28 - Quantity Extraction & Performance Optimization

### Major Improvements
- **Quantity Extraction Enhancement**: Achieved 98%+ extraction success rate (up from ~18% baseline)
- **Hybrid Processing System**: Fast HTTP requests with Playwright fallback for complex pages  
- **Performance Optimization**: Processing time reduced from hours to minutes for full exports
- **Export Preservation**: Fixed batch processing to preserve existing export directories

### Enhanced Bulgarian Support
- **Advanced Pattern Matching**: Native recognition of Bulgarian packaging units (г, кг, мл, л, грам, килограм)
- **Packaging Terminology**: Enhanced detection of "Опаковка" and variant forms
- **JSON-LD Prioritization**: Improved structured data extraction with intelligent fallbacks

### Technical Improvements
- **Smart Processing**: HTTP-first approach with Playwright only when needed
- **Robust Validation**: Added comprehensive validation scripts demonstrating 97.5-100% extraction rates
- **Error Handling**: Enhanced parsing resilience across diverse product page structures

### Validation Results
- Multiple test runs confirming 97.5-100% quantity extraction across all product categories
- Perfect preservation of Bulgarian language translations and currency formatting
- Successful processing of 55+ product categories with consistent quality

## [1.0.0] - 2025-09-27 - Initial Release

### Added
- Core scraper package `ebag_product_scraper` with basic HTML parsing
- CLI runner `ebag_runner.py` for category crawling and product extraction
- Playwright rendering support (`--render`) for JavaScript-heavy pages
- Image download and thumbnail generation (`--images-dir`, `--thumb-size`)
- Printable HTML generation with Bulgarian language support (`--lang bg`)
- Batch category processing via `--categories-file`
- Combined printable HTML output for multi-category exports

### Features  
- JSON-LD Product schema parsing with HTML fallbacks
- Auto-export functionality creating organized `exports/` structure
- Bulgarian currency mapping (BGN → лв., EUR → евро)
- Three-column printable layout for optimized page usage
- Category display name extraction from `<h1>` and `<title>` tags

### Technical Details
- Export directory cleanup at startup for fresh runs
- Normalized local image paths for file:// usage in printables
- PDF generation support via Playwright (optional)
- Comprehensive error handling and logging

### Requirements
- Python 3.8+
- BeautifulSoup4, requests for core functionality  
- Playwright (optional) for JavaScript rendering and PDF export
- Pillow for image processing and thumbnails

## [2.1.1] - 2025-11-30
### Changed
- Documentation: added last-updated marker and minor metadata fixes.
