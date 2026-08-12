FROM node:20-alpine AS builder
WORKDIR /app
COPY react/package.json react/package-lock.json* ./
RUN npm install --legacy-peer-deps
COPY react/ ./
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM node:20-alpine
RUN npm i -g serve
WORKDIR /app
COPY --from=builder /app/dist ./dist
EXPOSE 8501
CMD ["serve", "-s", "dist", "-l", "8501"]
