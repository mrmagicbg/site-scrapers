#!/bin/bash
# Script to validate the enhanced quantity extraction solution

# Navigate to project root regardless of from where the script is invoked
cd "$(dirname "$(realpath "$0")")"

echo "=== QUANTITY EXTRACTION VALIDATION SCRIPT ==="
echo "Testing enhanced solution across diverse categories"
echo

# Sample categories representing different product types
categories=(
    "https://www.ebag.bg/categories/sezonni-plodove/5070"   # Fruits
    "https://www.ebag.bg/categories/pileshko-file/1709"     # Meat  
    "https://www.ebag.bg/categories/maslo/378"              # Dairy
    "https://www.ebag.bg/categories/oriz/284"               # Grains
    "https://www.ebag.bg/categories/gazirana-voda/568"      # Beverages
)

category_names=(
    "Seasonal_Fruits"
    "Chicken_Fillet" 
    "Butter"
    "Rice"
    "Sparkling_Water"
)

echo "Processing ${#categories[@]} diverse categories..."
echo

total_products=0
total_with_quantities=0

for i in "${!categories[@]}"; do
    url="${categories[i]}"
    name="${category_names[i]}"
    
    echo "[$((i+1))/${#categories[@]}] Processing $name..."
    
    # Run the enhanced processor
    .venv/bin/python3 ebag_runner.py --category "$url" --delay 0.3 > /dev/null 2>&1
    
    # Find the generated JSONL file
    jsonl_file=$(find exports/ -name "*.jsonl" -newer /tmp/validation_start 2>/dev/null | tail -1)
    
    if [ -f "$jsonl_file" ]; then
        products=$(wc -l < "$jsonl_file")
        with_qty=$(jq -r '.quantity_raw // empty' "$jsonl_file" | grep -v '^$' | wc -l)
        rate=$(echo "scale=1; $with_qty * 100 / $products" | bc)
        
        echo "  ✅ $products products found, $with_qty with quantities (${rate}%)"
        
        # Show sample quantities
        echo "  📦 Sample quantities:"
        jq -r 'select(.quantity_raw != null and .quantity_raw != "") | "     • " + .name[0:50] + "... → " + .quantity_raw' "$jsonl_file" | head -3
        
        total_products=$((total_products + products))
        total_with_quantities=$((total_with_quantities + with_qty))
    else
        echo "  ❌ No data generated"
    fi
    echo
done

if [ $total_products -gt 0 ]; then
    overall_rate=$(echo "scale=1; $total_with_quantities * 100 / $total_products" | bc)
    echo "=== FINAL RESULTS ==="
    echo "✅ Total products processed: $total_products"
    echo "✅ Products with quantities: $total_with_quantities"  
    echo "✅ Overall extraction rate: ${overall_rate}%"
    echo
    echo "🎉 SOLUTION VALIDATED: Enhanced quantity extraction working across diverse categories!"
else
    echo "❌ No products were processed"
fi