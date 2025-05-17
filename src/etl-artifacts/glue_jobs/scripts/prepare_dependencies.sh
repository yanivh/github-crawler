#!/bin/bash

# Check if bucket name is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <s3-bucket-name>"
    exit 1
fi

BUCKET_NAME=$1
TEMP_DIR=$(mktemp -d)

echo "Creating temporary directory: $TEMP_DIR"

# Copy requirements.txt to S3
echo "Uploading requirements.txt to S3..."
aws s3 cp requirements.txt "s3://${BUCKET_NAME}/glue/requirements.txt"

# Create src.zip containing the source code
echo "Creating src.zip..."
cd ../../..  # Go to project root
zip -r "${TEMP_DIR}/src.zip" src/

# Upload src.zip to S3
echo "Uploading src.zip to S3..."
aws s3 cp "${TEMP_DIR}/src.zip" "s3://${BUCKET_NAME}/glue/src.zip"

# Upload Glue job scripts
echo "Uploading Glue job scripts..."
aws s3 cp IAC/terraform/glue/scripts/github_extract_job.py "s3://${BUCKET_NAME}/glue/scripts/github_extract_job.py"
aws s3 cp IAC/terraform/glue/scripts/github_transform_job.py "s3://${BUCKET_NAME}/glue/scripts/github_transform_job.py"

# Cleanup
echo "Cleaning up temporary directory..."
rm -rf "${TEMP_DIR}"

echo "Done! Dependencies uploaded to s3://${BUCKET_NAME}/glue/" 