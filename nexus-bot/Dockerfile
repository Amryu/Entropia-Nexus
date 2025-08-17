# Use an official Node LTS base image
FROM node:24-alpine AS base

# Set working directory
WORKDIR /app

# Install dependencies separately for caching
COPY package*.json ./
RUN npm ci --only=production

# Copy project files
COPY . .

# Expose app port (change if your app uses another port)
EXPOSE 3000

# Start the app
CMD ["node", "bot.js"]