# Use an official Node LTS base image
FROM node:24-alpine AS base

# Set working directory
WORKDIR /app

# Install dependencies separately for caching
COPY package*.json ./
RUN npm ci --only=production

# Copy project files
COPY ./build ./build
COPY start.js ./start.js

# Expose app port
EXPOSE 3001

# Start the app
CMD ["node", "start.js"]