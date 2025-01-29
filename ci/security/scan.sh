#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting security scan...${NC}"

# Check if Trivy is installed
if ! command -v trivy &> /dev/null; then
    echo -e "${RED}Trivy is not installed. Installing...${NC}"
    brew install trivy
fi

# Check if pip-audit is installed
if ! command -v pip-audit &> /dev/null; then
    echo -e "${RED}pip-audit is not installed. Installing...${NC}"
    pip install pip-audit
fi

# Build the Docker image locally
# echo -e "\n${YELLOW}Building Docker image for scanning...${NC}"
IMAGE_NAME="ghcr.io/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\([^/]*\)\/.*/\1/')/agent-runtime:test"
docker build -t "$IMAGE_NAME" -f Dockerfile .

# Variables
SEVERITY="HIGH,CRITICAL"
EXIT_CODE=0

echo -e "\n${YELLOW}Scanning container image for vulnerabilities...${NC}"
if ! trivy image --severity $SEVERITY --exit-code 1 --ignore-unfixed "$IMAGE_NAME"; then
    echo -e "${RED}Container vulnerabilities found!${NC}"
    EXIT_CODE=1
fi

echo -e "\n${YELLOW}Scanning Python dependencies for known vulnerabilities...${NC}"

# Generate requirements.txt from poetry
echo -e "\n${YELLOW}Generating requirements.txt from poetry...${NC}"
poetry export -f requirements.txt --output requirements.txt --without-hashes

echo -e "\n${YELLOW}Scanning dependencies for vulnerabilities...${NC}"
if ! pip-audit -r requirements.txt; then
    echo -e "${RED}Python package vulnerabilities found!${NC}"
    EXIT_CODE=1
fi

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}Security scan completed successfully. No high or critical vulnerabilities found.${NC}"
else
    echo -e "\n${RED}Security scan failed. Please address the vulnerabilities above.${NC}"
fi

exit $EXIT_CODE
