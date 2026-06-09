FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* /app/
RUN npm install --omit=dev

COPY src /app/src

EXPOSE 8000

CMD ["node", "src/index.js"]
