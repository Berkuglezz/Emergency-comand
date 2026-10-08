# Imagen de desarrollo del frontend (Vite + pnpm).
FROM node:24-slim

RUN npm install --global pnpm@12.9.1

WORKDIR /app

# Capa de dependencias: solo se reconstruye si cambian package.json o el lockfile.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store

COPY . .

EXPOSE 5173

CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
