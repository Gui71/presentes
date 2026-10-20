# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
# CA adicional opcional via secret efêmero de build; verificação TLS continua ativa.
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    /opt/venv/bin/pip install -r /tmp/requirements.txt

FROM python:3.12-slim-bookworm AS app
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STATIC_ROOT=/opt/static TEST_DATABASE_PATH=/tmp/presentes-tests.sqlite3
RUN groupadd --gid 10001 presentes && useradd --uid 10001 --gid presentes --no-create-home presentes \
    && mkdir -p /app /var/lib/presentes/db /var/lib/presentes/media /opt/static \
    && chown -R 10001:10001 /var/lib/presentes /opt/static
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /app
COPY --chown=10001:10001 manage.py requirements.txt ./
COPY --chown=10001:10001 config ./config
COPY --chown=10001:10001 gifts ./gifts
COPY --chown=10001:10001 templates ./templates
COPY --chown=10001:10001 static ./static
USER 10001:10001
RUN python -c "import os,secrets,django;os.environ.update(APP_ENV='test',SECRET_KEY=secrets.token_urlsafe(64),DJANGO_SETTINGS_MODULE='config.settings');django.setup();from django.core.management import call_command;call_command('collectstatic',interactive=False,verbosity=0)"
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "45", "--access-logfile", "-", "--access-logformat", "%(m)s %(U)s %(s)s", "--error-logfile", "-"]

FROM caddy:2.10-alpine AS proxy
RUN setcap -r /usr/bin/caddy \
    && mkdir -p /data/caddy /config/caddy && chown -R 10001:10001 /data /config
COPY --from=app --chown=10001:10001 /opt/static /srv/static
COPY --chown=10001:10001 deploy/Caddyfile /etc/caddy/Caddyfile
USER 10001:10001
