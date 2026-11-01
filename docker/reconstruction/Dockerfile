# Isolated reconstruction study; the normal docker/mariadb build is unchanged.
FROM mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112
USER root
COPY reconstruction /usr/local/share/reconstruction
RUN set -eu; \
    . /etc/os-release; test "$VERSION_ID" = 24.04; \
    test -s /usr/share/keyrings/ubuntu-archive-keyring.gpg; \
    test -s /etc/apt/trusted.gpg.d/mariadb.gpg; \
    rm -f /etc/apt/sources.list /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; \
    cp /usr/local/share/reconstruction/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources; \
    cp /usr/local/share/reconstruction/mariadb.list /etc/apt/sources.list.d/mariadb.list; \
    apt-get update; \
    (cd /var/lib/apt/lists && sha256sum -c /usr/local/share/reconstruction/inrelease.sha256); \
    mkdir -p /usr/local/share/reconstruction/indexes /usr/local/share/reconstruction/packages /usr/local/share/reconstruction/keys; \
    cp /usr/share/keyrings/ubuntu-archive-keyring.gpg /etc/apt/trusted.gpg.d/mariadb.gpg /usr/local/share/reconstruction/keys/; \
    (cd /usr/local/share/reconstruction/keys && sha256sum ./*.gpg > SHA256SUMS.txt); \
    cp /var/lib/apt/lists/*_InRelease /var/lib/apt/lists/*_Packages* /usr/local/share/reconstruction/indexes/; \
    DEBIAN_FRONTEND=noninteractive apt-get \
      -o Dir::Cache::archives=/usr/local/share/reconstruction/packages \
      install -y --no-install-recommends mariadb-plugin-rocksdb=1:11.8.9+maria~ubu2404; \
    test "$(dpkg-query -W -f='${Version}' mariadb-server-core)" = '1:11.8.9+maria~ubu2404'; \
    test "$(dpkg-query -W -f='${Version}' mariadb-plugin-rocksdb)" = '1:11.8.9+maria~ubu2404'; \
    (cd /usr/local/share/reconstruction/packages && sha256sum ./*.deb > SHA256SUMS.txt); \
    dpkg-query -W -f='${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n' \
      > /usr/local/share/reconstruction/installed-packages.txt; \
    rm -rf /var/lib/apt/lists/* /usr/local/share/reconstruction/packages/partial; \
    rm -f /usr/local/share/reconstruction/packages/lock
COPY mariadb/rocksdb.cnf /etc/mysql/mariadb.conf.d/rocksdb.cnf
