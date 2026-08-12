FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps

FROM node:22-alpine AS builder
WORKDIR /app
ARG BACKEND_URL=http://backend:8003
ENV NEXT_PUBLIC_API_URL=$BACKEND_URL
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS pkgpatch
WORKDIR /pkg
RUN npm pack cross-spawn@7.0.5 glob@10.5.0 minimatch@10.2.3 tar@7.5.11 picomatch@4.0.4 2>&1 | tail -3 &&     mkdir -p /out/cross-spawn /out/glob /out/minimatch /out/tar /out/picomatch &&     tar -xzf cross-spawn-7.0.5.tgz --strip-components=1 -C /out/cross-spawn &&     tar -xzf glob-10.5.0.tgz --strip-components=1 -C /out/glob &&     tar -xzf minimatch-10.2.3.tgz --strip-components=1 -C /out/minimatch &&     tar -xzf tar-7.5.11.tgz --strip-components=1 -C /out/tar &&     tar -xzf picomatch-4.0.4.tgz --strip-components=1 -C /out/picomatch

FROM node:22-alpine AS runner
WORKDIR /app
COPY --from=pkgpatch /out/cross-spawn/ /usr/local/lib/node_modules/npm/node_modules/cross-spawn/
COPY --from=pkgpatch /out/glob/        /usr/local/lib/node_modules/npm/node_modules/glob/
COPY --from=pkgpatch /out/minimatch/   /usr/local/lib/node_modules/npm/node_modules/minimatch/
COPY --from=pkgpatch /out/tar/         /usr/local/lib/node_modules/npm/node_modules/tar/
COPY --from=pkgpatch /out/picomatch/   /usr/local/lib/node_modules/npm/node_modules/picomatch/

ENV NODE_ENV=production
RUN adduser -D -u 1001 nextjs
RUN mkdir -p ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
