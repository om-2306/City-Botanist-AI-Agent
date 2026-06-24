#!/bin/bash
# City Botanist Deployment Script
# This script builds the Docker image and deploys it to Google Cloud Run.

set -e

# Configuration variables
PROJECT_NAME="citybotanist"
GCP_PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
IMAGE_TAG="gcr.io/${GCP_PROJECT_ID}/${PROJECT_NAME}:latest"

echo "=== City Botanist Deployment ==="

# Step 1: Check environment variables
if [ "$GCP_PROJECT_ID" = "your-gcp-project-id" ]; then
    echo "WARNING: Please update the GCP_PROJECT_ID in deploy.sh before deploying."
    echo "To run locally, you can use: docker build -t ${PROJECT_NAME} . && docker run -p 8501:8501 --env-file .env ${PROJECT_NAME}"
    exit 1
fi

# Step 2: Build the Docker image
echo "Building Docker image..."
docker build -t ${PROJECT_NAME} .

# Step 3: Tag and Push to Google Container Registry / Artifact Registry
echo "Tagging Docker image for Google Cloud Container Registry..."
docker tag ${PROJECT_NAME} ${IMAGE_TAG}

echo "Pushing Docker image to GCR..."
docker push ${IMAGE_TAG}

# Step 4: Deploy to Google Cloud Run
echo "Deploying to Google Cloud Run..."
gcloud run deploy ${PROJECT_NAME} \
    --image ${IMAGE_TAG} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --port 8501

echo "Deployment completed successfully!"
