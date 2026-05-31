#!/bin/bash

# Step 1: Update the requirements.txt file and save it into the original path
pip freeze > requirements_all_freeze.txt

# Step 2: Check if the 'packages' directory exists. If it does, clean it. If not, create it.
PACKAGES_DIR="./packages"
if [ -d "$PACKAGES_DIR" ]; then
    # The directory exists, so remove its contents
    rm -rf "${PACKAGES_DIR:?}"/*
else
    # The directory does not exist, so create it
    mkdir -p "$PACKAGES_DIR"
fi

# Step 3: Download the packages listed in requirements.txt into the specified directory
pip download -r requirements_all_freeze.txt -d "$PACKAGES_DIR"

# Step 4: Print a completion message
echo "requirements_all_freeze.txt has been updated and necessary packages have been downloaded."
