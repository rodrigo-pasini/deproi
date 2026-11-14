# A disposable "server" for Deproi's end-to-end test: sshd, sudo, git, Python 3.10
# (Ubuntu 22.04, the oldest supported) and the Docker CLI talking to the host's
# daemon through the mounted socket.
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-server sudo git python3 docker.io docker-compose-v2 \
      ca-certificates util-linux bsdutils procps \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /run/sshd \
 && ssh-keygen -A \
 && printf 'PasswordAuthentication no\nPermitRootLogin no\n' > /etc/ssh/sshd_config.d/deproi-e2e.conf
EXPOSE 22
CMD ["/usr/sbin/sshd", "-D", "-e"]
