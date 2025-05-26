#!/bin/bash
set -e

# Configuration - Use Docker Hub instead of GHCR
REGISTRY="docker.io"
USERNAME="${DOCKER_USERNAME:-jacsamell}"
IMAGE_NAME="pr-agent"
TAG="${1:-latest}"

echo "🐳 Building PR-Agent Docker image..."
echo "Registry: $REGISTRY"
echo "Username: $USERNAME"
echo "Image: $IMAGE_NAME"
echo "Tag: $TAG"

# Build the image for linux/amd64 (GitHub Actions compatibility)
echo "📦 Building image for linux/amd64..."
docker build --platform linux/amd64 -f Dockerfile.github_action -t "$REGISTRY/$USERNAME/$IMAGE_NAME:$TAG" .

# Login to registry (requires DOCKER_PASSWORD environment variable)
if [ -n "$DOCKER_PASSWORD" ]; then
    echo "🔐 Logging in to $REGISTRY..."
    echo "$DOCKER_PASSWORD" | docker login "$REGISTRY" -u "$USERNAME" --password-stdin
else
    echo "⚠️  DOCKER_PASSWORD not set. Please login manually:"
    echo "   docker login $REGISTRY"
fi

# Push the image
echo "🚀 Pushing image..."
docker push "$REGISTRY/$USERNAME/$IMAGE_NAME:$TAG"

echo "✅ Image pushed successfully!"
echo "📋 Use in GitHub Actions:"
echo "   uses: docker://$REGISTRY/$USERNAME/$IMAGE_NAME:$TAG" 