FROM node:20-alpine

WORKDIR /app

# Copy package configuration files and install dependencies
COPY package*.json ./
RUN npm install

# Copy application files
COPY . .

# Build Next.js app
RUN npm run build

# Expose port 3000
EXPOSE 3000

# Start production server
CMD ["npm", "run", "start"]
