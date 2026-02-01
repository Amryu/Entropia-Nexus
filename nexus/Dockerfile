# Use an official Node LTS base image
FROM node:24-alpine AS base

# Install dependencies for sharp (image processing)
RUN apk add --no-cache \
    vips-dev \
    fftw-dev \
    build-base \
    python3

# Set working directory
WORKDIR /app

# Install dependencies separately for caching
COPY package*.json ./
RUN npm ci --only=production

# Remove build dependencies to reduce image size
RUN apk del build-base python3

# Copy project files
COPY ./build ./build
COPY start.js ./start.js

# Create uploads directory with proper permissions
# This will be mounted as a volume in production
RUN mkdir -p /app/uploads/temp /app/uploads/pending /app/uploads/approved \
    && chown -R node:node /app/uploads

# Set environment variable for uploads directory
ENV UPLOAD_DIR=/app/uploads

# Use non-root user for security
USER node

# Expose app port
EXPOSE 3001

# Start the app
CMD ["node", "start.js"]
