FROM mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112
USER root
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       mariadb-plugin-rocksdb=1:11.8.9+maria~ubu2404 \
    && test "$(dpkg-query -W -f='${Version}' mariadb-server-core)" = '1:11.8.9+maria~ubu2404' \
    && rm -rf /var/lib/apt/lists/*
# Replace the package's config so the plugin is loaded once, on every startup.
COPY rocksdb.cnf /etc/mysql/mariadb.conf.d/rocksdb.cnf
