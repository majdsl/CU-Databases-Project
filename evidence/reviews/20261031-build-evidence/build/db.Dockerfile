FROM mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112
USER root
RUN --mount=type=secret,id=cloud_ca,required=true apt-get -o Acquire::https::CaInfo=/run/secrets/cloud_ca update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::https::CaInfo=/run/secrets/cloud_ca install -y --no-install-recommends \
       mariadb-plugin-rocksdb=1:11.8.9+maria~ubu2404 \
    && test "$(dpkg-query -W -f='${Version}' mariadb-server-core)" = '1:11.8.9+maria~ubu2404' \
    && rm -rf /var/lib/apt/lists/*
# Replace the package's config so the plugin is loaded once, on every startup.
COPY --chmod=0755 rocksdb.cnf /etc/mysql/mariadb.conf.d/rocksdb.cnf
