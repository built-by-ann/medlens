# syntax=docker/dockerfile:1
# Pins the BuildKit Dockerfile frontend version so `--mount=type=cache`
# below (Issue #184) is recognized consistently regardless of the exact
# Docker Engine version running this build.

# Build stage: compiles the SPA to static files. Node is only needed to
# run the build - the runtime stage below never sees it.
FROM node:20-alpine AS builder

WORKDIR /app

# A lockfile is committed, so `npm ci` (exact, reproducible install) is
# correct here, not `npm install` - same reasoning as frontend.yml's CI
# install step.
COPY package.json package-lock.json ./
# --mount=type=cache (Issue #184): npm's own download cache (~/.npm)
# persists across builds via a BuildKit cache mount rather than living in
# this layer - `npm ci` still verifies/reinstalls into node_modules from
# the lockfile every time (unchanged, reproducible installs are the whole
# point of npm ci), but a lockfile change no longer means redownloading
# every package tarball from the registry - see this issue's final report
# for measured before/after numbers.
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY . .

# Vite inlines import.meta.env.VITE_API_BASE_URL into the built JS bundle
# at build time - there is no way to change it at container start like a
# normal runtime environment variable, since by then the static files are
# already fixed. The default below matches .env.example / frontend.yml's
# CI value, so the image builds standalone with no required arguments;
# override it for a real deployment with
# `docker build --build-arg VITE_API_BASE_URL=https://api.example.com`.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# Runtime stage: nginx serving the prebuilt static files - no Node, no
# source, no node_modules in the final image.
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
