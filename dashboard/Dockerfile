# Service dashboard Soukna — Next.js (landing + dashboards admin/entreprise)
FROM node:20-alpine AS build
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* est gravé dans le bundle à la génération : la valeur
# arrive en build-arg (CI) ou vaut le défaut local.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

COPY --from=build /app ./

EXPOSE 3000
CMD ["npm", "run", "start"]
