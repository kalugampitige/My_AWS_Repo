#!/bin/bash
set -e

FUNCTION_NAME="mail-clerk-agent"
BUILD_DIR="./package"
ZIP_FILE="deployment.zip"

echo "=== Packaging AI Mail Clerk Agent ==="

# Clean up previous builds
rm -rf $BUILD_DIR $ZIP_FILE

# Install dependencies into package folder
mkdir -p $BUILD_DIR
pip install -r requirements.txt --target $BUILD_DIR --upgrade

# Compress dependencies
cd $BUILD_DIR
zip -r ../$ZIP_FILE .
cd ..

# Add python source code and JSON files to zip root
zip -g $ZIP_FILE *.py institutes.json

echo "=== Uploading package to AWS Lambda ==="
aws lambda update-function-code \
  --function-name $FUNCTION_NAME \
  --zip-file fileb://$ZIP_FILE

echo "=== Deployment Complete ==="