FROM node:24-alpine
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api-client/package.json packages/api-client/package.json
RUN npm ci
COPY apps/web apps/web
COPY packages/api-client packages/api-client
EXPOSE 5173
CMD ["npm", "run", "dev", "-w", "apps/web", "--", "--host", "0.0.0.0"]
