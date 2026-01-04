#!/bin/bash

# Script to build and fix the Next.js standalone build for production deployment
# This script resolves the missing module issues in the standalone build

set -e  # Exit on any error

echo "🚀 Starting frontend compilation for standalone deployment..."

# 1. Clean up any cached files that might cause issues
echo "🧹 Cleaning up cache and lock files..."
rm -rf apps/www/.contentlayer
rm -rf apps/www/.next
rm -rf node_modules/.cache

# 2. Build the frontend from the apps/www directory
echo "📦 Building frontend with pnpm..."
cd apps/www

# Force ContentLayer to regenerate cache by cleaning and rebuilding
echo "🔄 Regenerating ContentLayer cache..."
rm -rf .contentlayer

# Check if pnpm is available, if not try to use it directly
echo "🏗️  Building the application..."
if ! command -v pnpm &> /dev/null; then
    echo "⚠️  pnpm not found, trying npx pnpm..."
    npx pnpm@latest build
else
    pnpm build
fi

echo "🔧 Fixing standalone build dependencies..."

# 3. Prepare for minimal dependency copying (done later)

# 4. Copy essential public assets only (excluding large demo files)
echo "🖼️  Copying essential public assets..."
mkdir -p .next/standalone/public
# Copy essential files only, excluding large demo images
cp public/favicon.ico .next/standalone/public/ 2>/dev/null || true
cp public/placeholder*.* .next/standalone/public/ 2>/dev/null || true
cp public/schema.json .next/standalone/public/ 2>/dev/null || true
cp -r public/r .next/standalone/public/ 2>/dev/null || true
cp -r public/registry .next/standalone/public/ 2>/dev/null || true
# Copy smaller image assets only (skip large demo images)
mkdir -p .next/standalone/public/images
cp public/images/style*.jpg .next/standalone/public/images/ 2>/dev/null || true
# Copy smaller avatars
cp -r public/avatars .next/standalone/public/ 2>/dev/null || true

# 5. Copy static assets to the correct location for standalone
echo "⚡ Ensuring static assets are in place..."
cp -r .next/static .next/standalone/.next/ 2>/dev/null || true

# 6. Create minimal node_modules with only essential files
echo "🔗 Creating minimal node_modules for standalone..."
rm -rf .next/standalone/node_modules
mkdir -p .next/standalone/node_modules

# Copy only essential Next.js files for server-side operation
echo "📦 Copying minimal Next.js dependencies..."
mkdir -p .next/standalone/node_modules/next/dist
# Find the Next.js module dynamically
NEXT_SRC=$(find ../../node_modules/.pnpm -type d -name "next" -path "*next@14*" | grep "/node_modules/next$" | head -1)
if [ -z "$NEXT_SRC" ]; then
    echo "⚠️  Could not find Next.js in pnpm store, trying fallback..."
    NEXT_SRC="../../node_modules/next"
fi
echo "📍 Using Next.js from: $NEXT_SRC"

# Copy essential server-side directories only
cp -r $NEXT_SRC/dist/server .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/shared .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/build .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/lib .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/styled-jsx .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/telemetry .next/standalone/node_modules/next/dist/
cp -r $NEXT_SRC/dist/trace .next/standalone/node_modules/next/dist/
# Copy essential client directory (required for server-side routing)
cp -r $NEXT_SRC/dist/client .next/standalone/node_modules/next/dist/

# Copy essential compiled dependencies (just copy the whole thing but exclude huge ones)
echo "📦 Copying essential compiled dependencies..."
mkdir -p .next/standalone/node_modules/next/dist/compiled
# Copy the whole compiled directory but exclude the largest packages
rsync -av --exclude='webpack' --exclude='terser' --exclude='sass' --exclude='postcss*' --exclude='babel-*' --exclude='@babel/core' $NEXT_SRC/dist/compiled/ .next/standalone/node_modules/next/dist/compiled/ 2>/dev/null || {
    # Fallback: copy everything if rsync not available
    cp -r $NEXT_SRC/dist/compiled/* .next/standalone/node_modules/next/dist/compiled/ 2>/dev/null || true
}

cp $NEXT_SRC/package.json .next/standalone/node_modules/next/

# Copy minimal React (find dynamically)
mkdir -p .next/standalone/node_modules/react
REACT_SRC=$(find ../../node_modules/.pnpm -type d -path "*react@18*/node_modules/react" ! -path "*react-dom*" | head -1)
if [ -n "$REACT_SRC" ]; then
    echo "📍 Using React from: $REACT_SRC"
    cp -r $REACT_SRC/* .next/standalone/node_modules/react/ 2>/dev/null || true
else
    cp -r ../../node_modules/react/* .next/standalone/node_modules/react/ 2>/dev/null || true
fi

# Copy minimal React DOM (find dynamically)
mkdir -p .next/standalone/node_modules/react-dom
REACT_DOM_SRC=$(find ../../node_modules/.pnpm -type d -path "*react-dom@18*/node_modules/react-dom" | head -1)
if [ -n "$REACT_DOM_SRC" ]; then
    echo "📍 Using React DOM from: $REACT_DOM_SRC"
    cp -r $REACT_DOM_SRC/* .next/standalone/node_modules/react-dom/ 2>/dev/null || true
else
    cp -r ../../node_modules/react-dom/* .next/standalone/node_modules/react-dom/ 2>/dev/null || true
fi

# Copy minimal styled-jsx (find dynamically)
mkdir -p .next/standalone/node_modules/styled-jsx
STYLED_JSX_SRC=$(find ../../node_modules/.pnpm -type d -path "*styled-jsx@5*/node_modules/styled-jsx" | head -1)
if [ -n "$STYLED_JSX_SRC" ]; then
    echo "📍 Using styled-jsx from: $STYLED_JSX_SRC"
    cp -r $STYLED_JSX_SRC/* .next/standalone/node_modules/styled-jsx/ 2>/dev/null || true
else
    echo "⚠️  Could not find styled-jsx, trying fallback..."
    cp -r ../../node_modules/styled-jsx/* .next/standalone/node_modules/styled-jsx/ 2>/dev/null || true
fi

# Copy only essential @next/env files
mkdir -p .next/standalone/node_modules/@next/env
if [ -d "../../node_modules/@next/env" ]; then
    cp -r ../../node_modules/@next/env/{package.json,dist} .next/standalone/node_modules/@next/env/ 2>/dev/null || true
fi

# Copy minimal SWC helpers
mkdir -p .next/standalone/node_modules/@swc/helpers
if [ -d "../../node_modules/@swc/helpers" ]; then
    cp -r ../../node_modules/@swc/helpers/{package.json,esm,lib,cjs} .next/standalone/node_modules/@swc/helpers/ 2>/dev/null || true
fi

# 7. Create zip file of standalone build
echo "📦 Creating zip file of standalone build..."
cd ../..
rm -rf ../yaaaf/client/standalone ../yaaaf/client/standalone.zip

# Create zip file from the standalone build
echo "🗜️  Zipping standalone build..."
cd apps/www/.next
zip -r ../../../../yaaaf/client/standalone.zip standalone/ -q

echo "✅ Standalone build compilation complete!"
echo ""
echo "📦 Standalone build zipped to: ../yaaaf/client/standalone.zip"
echo "📏 Zip file size: $(du -sh ../../../../yaaaf/client/standalone.zip | cut -f1)"
echo ""
echo "🎯 The Python backend will automatically unzip and run the server"