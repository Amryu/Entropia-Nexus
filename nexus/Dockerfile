# Use an official Node LTS base image
FROM node:18-alpine AS base

# Set working directory
WORKDIR /app

# Install dependencies separately for caching
COPY package*.json ./
RUN npm ci --only=production

# Copy project files
COPY . .

# Expose app port (change if your app uses another port)
EXPOSE 3001

# Start the app
CMD ["node", "start.js"]