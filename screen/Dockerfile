FROM node:24-bookworm-slim@sha256:dc26ae92c9fb15cf6b1d63e20f0944b2efe0f115b20e00be48fb23fceb061c54 AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
COPY web/package.json web/package.json
COPY screen/package.json screen/package.json
RUN npm ci
COPY screen/src screen/src
COPY packages packages

COPY screen/index.html screen/tsconfig.json screen/vite.config.ts screen/
RUN npm run build --workspace screen

FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b AS dependencies
WORKDIR /build
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt package-lock.json ./
RUN pip install --no-cache-dir --upgrade pip==26.3 && pip install --no-cache-dir -r requirements.txt
COPY scripts scripts
COPY --from=frontend /build/node_modules node_modules
RUN python -m scripts.desktop_notices

FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b AS runtime
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip==26.3 \
    && useradd --uid 10001 --create-home studio \
    && mkdir -p /app /data && chown studio:studio /data && chmod 700 /data
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHON_DOTENV_DISABLED=1 STUDIO_DATA_DIR=/data
WORKDIR /app
COPY --from=dependencies /opt/venv /opt/venv
COPY apps/api apps/api
COPY apps/version.py apps/version.py
COPY data data
COPY --from=frontend /build/packages/domain-schemas packages/domain-schemas
COPY scripts/manage.py scripts/backup_restore.py scripts/convert_ifc.py scripts/
COPY web/*.py web/
COPY web/config web/config
COPY screen/*.py screen/
COPY screen/data screen/data
COPY --from=frontend /build/screen/dist screen/dist
COPY --from=dependencies /build/runtime/desktop-notices notices
RUN /usr/local/bin/python -m pip uninstall --yes pip \
    && /opt/venv/bin/python -m pip uninstall --yes pip
USER 10001:10001
EXPOSE 8090
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/api/v1/health', timeout=3)"
ENTRYPOINT ["python", "-m", "screen.server"]
