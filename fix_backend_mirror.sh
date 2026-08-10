#!/bin/bash
set -e

# Dockerfile is versioned so deployments remain reproducible. Mirror changes
# must be reviewed and committed instead of mutating a production worktree.
echo "backend/Dockerfile 已由 Git 统一管理，无需动态修补镜像源。"
