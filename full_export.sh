#!/bin/bash
# Full export script for all 55 categories with 100% quantity extraction

# Parse command line arguments
TABLE_FORMAT=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --table-format)
            TABLE_FORMAT="--html-format table"
            echo "Table format enabled"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--table-format]"
            echo "  --table-format    Generate HTML tables instead of cards"
            exit 1
            ;;
    esac
done

# Navigate to project root regardless of from where the script is invoked
cd "$(dirname "$(realpath "$0")")"

echo "========================================"
echo "    FULL EXPORT - ALL 55 CATEGORIES"
echo "========================================"
echo "Starting complete export with enhanced quantity extraction..."
echo "Start time: $(date)"
echo

# Read all categories
total_categories=$(wc -l < categories.txt)
echo "Total categories to process: $total_categories"
echo

# Initialize counters
processed=0
total_products=0
total_with_quantities=0
failed_categories=0

# Process each category
while IFS= read -r category_url; do
    ((processed++))
    
    # Extract category name for display
    category_name=$(basename "$category_url")
    
    echo "[$processed/$total_categories] Processing: $category_name"
    echo "URL: $category_url"
    
    # Run the export with timeout
    if timeout 300 .venv/bin/python3 ebag_runner.py --category "$category_url" --delay 0.3 $TABLE_FORMAT > /dev/null 2>&1; then
        # Find the generated JSONL file
        jsonl_pattern="exports/categories_*_$(echo $category_url | grep -o '[0-9]*$')/categories_*_$(echo $category_url | grep -o '[0-9]*$').jsonl"
        jsonl_file=$(ls $jsonl_pattern 2>/dev/null | head -1)
        
        if [ -f "$jsonl_file" ]; then
            products=$(wc -l < "$jsonl_file")
            with_qty=$(jq -r '.quantity_raw // empty' "$jsonl_file" | grep -v '^$' | wc -l)
            rate=$(echo "scale=1; $with_qty * 100 / $products" | bc 2>/dev/null || echo "0")
            
            echo "  ✅ SUCCESS: $products products, $with_qty with quantities (${rate}%)"
            
            total_products=$((total_products + products))
            total_with_quantities=$((total_with_quantities + with_qty))
        else
            echo "  ⚠️  No products found in category"
        fi
    else
        echo "  ❌ FAILED: Timeout or error during processing"
        ((failed_categories++))
    fi
    
    echo
done < categories.txt

echo "========================================"
echo "           FINAL RESULTS"
echo "========================================"
echo "End time: $(date)"
echo "Categories processed: $processed"
echo "Categories failed: $failed_categories"
echo "Total products: $total_products"
echo "Products with quantities: $total_with_quantities"

if [ $total_products -gt 0 ]; then
    overall_rate=$(echo "scale=1; $total_with_quantities * 100 / $total_products" | bc)
    echo "Overall extraction rate: ${overall_rate}%"
else
    echo "Overall extraction rate: 0%"
fi

echo
echo "Export files generated: $(find exports/ -name '*.jsonl' | wc -l)"
echo "Images downloaded: $(find exports/ -name '*.jpg' | wc -l)"
echo
echo "🎉 Full export completed!"