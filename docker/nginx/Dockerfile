FROM nginx:latest

COPY ./docker/nginx/ssl.conf /etc/nginx/conf.d/ssl.conf
COPY ./docker/nginx/index.html /usr/share/nginx/html

RUN : \
    && mkdir -p /etc/nginx/certs \
    && openssl req -x509 -nodes -newkey rsa:2048 \
                    -days 365 \
                    -keyout  /etc/nginx/certs/self.key \
                    -out     /etc/nginx/certs/self.crt \
                    -subj    "/CN=host" \
    && ls -l /etc/nginx/certs/ \
    && :
