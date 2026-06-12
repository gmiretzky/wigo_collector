#!/usr/bin/env bash
set -euo pipefail

IMAGE="gmiretzky/wigo-controller"
TAG="${1:-latest}"

echo "[*] Building ${IMAGE}:${TAG} ..."
docker build \
  -f docker/controller/Dockerfile \
  -t "${IMAGE}:${TAG}" \
  -t "${IMAGE}:latest" \
  .

echo "[*] Pushing ${IMAGE}:${TAG} ..."
docker push "${IMAGE}:${TAG}"
if [ "${TAG}" != "latest" ]; then
  docker push "${IMAGE}:latest"
fi

echo "[+] Done — ${IMAGE}:${TAG} is live on Docker Hub"
