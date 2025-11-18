#!/bin/bash

echo "Checking file structure..."
echo ""

# Define required files and directories
required_dirs=("static" "static/css" "static/js" "templates" "tests")
required_files=(
    "app.py" "models.py" "auth.py" "utils.py"
    "requirements.txt" ".env.example" "vercel.json"
    "static/css/style.css" "static/js/main.js"
    "templates/base.html" "templates/index.html" 
    "templates/login.html" "templates/signup.html"
    "templates/dashboard.html" "templates/pricing.html"
    "tests/test_auth.py" "tests/test_shortener.py"
    "tests/test_integration.py" "api-integration.md"
)

# Check directories
echo "📁 Checking directories..."
for dir in "${required_dirs[@]}"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir"
    else
        echo "❌ $dir (missing)"
    fi
done

echo ""
echo "📄 Checking files..."
# Check files
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (missing)"
    fi
done

echo ""
echo "Complete! You can now paste the code into each file."
