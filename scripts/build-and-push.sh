#!/bin/bash

# GitHub PR Bot - Build and Push Script
# Builds multi-platform Docker image and pushes to GitHub Container Registry

set -e

# Configuration
IMAGE_NAME="ghcr.io/jacsamell/github-pr-bot"
DOCKERFILE="Dockerfile.github_action"

echo "🚀 Building GitHub PR Bot Docker image..."

# Create buildx builder if it doesn't exist
if ! docker buildx ls | grep -q "multiarch"; then
    echo "📦 Creating multi-platform builder..."
    docker buildx create --use --name multiarch --driver docker-container
fi

# Use the multiarch builder
docker buildx use multiarch

# Build and push multi-platform image with both latest and v1 tags
echo "🔨 Building and pushing multi-platform image..."
docker buildx build \
    --platform linux/amd64,linux/arm64 \
    --file $DOCKERFILE \
    --tag $IMAGE_NAME:latest \
    --tag $IMAGE_NAME:v1 \
    --push \
    .

echo "✅ Successfully built and pushed $IMAGE_NAME:latest and $IMAGE_NAME:v1"
echo "🎯 Image supports: linux/amd64, linux/arm64"
echo ""
echo "To use in GitHub Actions:"
echo "  uses: docker://$IMAGE_NAME:latest"
echo "  uses: docker://$IMAGE_NAME:v1" 