FROM node:22-alpine as builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install
COPY . .
RUN npm run build

FROM caddy:alpine

COPY --from=builder /app/dist /usr/share/caddy
CMD ["caddy"]
