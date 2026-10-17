"""Render separate HTTPS vhosts with query-free structured access logs."""

import argparse
import re
from pathlib import Path

HTTP = r"""
map $server_name $juya_environment {
    default production;
    ~^test- test;
}
map $server_name $juya_service {
    default unknown;
    ~^(test-)?admin-api\. admin-api;
    ~^(test-)?api\. mini-api;
    ~^(test-)?admin\. admin-web;
    ~^(test-)?h5\. retired-h5;
}
map $uri $juya_kind {
    default static;
    ~^/health/ health;
    ~^/api/(admin|mini)/v1/auth/ auth;
    ~^/api/(admin|mini)/v1/(media|pronunciation)(/|$) media;
    ~pronunciation$ cloud;
    ~^/api/(admin|mini)/v1/imports uploads;
    ~^/api/(admin|mini)/v1/ business;
}
map "$uri:$status" $juya_admin_cache {
    default no-store;
    ~^/assets/[^:]+:200$ "public, max-age=31536000, immutable";
}
log_format juya_safe escape=json
    '{"time":$msec,"environment":"$juya_environment","service":"$juya_service",'
    '"kind":"$juya_kind","method":"$request_method","status":$status,'
    '"seconds":$request_time,"request_id":"$request_id"}';
"""

PROXY = r"""
proxy_http_version 1.1;
proxy_set_header Connection "";
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto https;
proxy_set_header X-Forwarded-For $remote_addr;
proxy_set_header X-Request-ID $request_id;
proxy_set_header Range $http_range;
proxy_set_header If-Range $http_if_range;
proxy_connect_timeout 5s;
proxy_read_timeout 180s;
proxy_send_timeout 180s;
proxy_buffering off;
proxy_hide_header Server;
"""


def render(environment, certificate, key, includes="/etc/nginx/juya-rebuild"):
    if environment not in ("test", "production"):
        raise ValueError("explicit environment required")
    for value in (certificate, key, includes):
        if not re.fullmatch(r"/[A-Za-z0-9_./-]+", value) or ".." in value.split("/"):
            raise ValueError("invalid absolute Nginx file path")
    prefix = "test-" if environment == "test" else ""
    base = 18000 if environment == "test" else 28000
    tls = f"""
    listen 443 ssl;
    ssl_certificate {certificate};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
    access_log /var/log/nginx/juya-rebuild-access.jsonl juya_safe;
    # Default error messages can contain signed resource paths. Safe access metrics carry failures.
    error_log /dev/null crit;
    add_header X-Content-Type-Options nosniff always;
    add_header Referrer-Policy no-referrer always;
    add_header X-Frame-Options DENY always;
"""
    domains = [prefix + part + ".juyayingyu.com" for part in ("admin", "admin-api", "api", "h5")]
    blocks = [
        f"""server {{
    listen 80;
    server_name {" ".join(domains)};
    access_log /var/log/nginx/juya-rebuild-access.jsonl juya_safe;
    error_log /dev/null crit;
    location ^~ /.well-known/acme-challenge/ {{ root /var/www/juya-acme; }}
    location / {{ return 308 https://$host$request_uri; }}
}}
"""
    ]
    for role, domain, port in [("admin", domains[1], base + 1), ("mini", domains[2], base + 2)]:
        blocks.append(f"""server {{
    server_name {domain};
{tls}
    client_max_body_size 110m;
    client_body_timeout 120s;
    include {includes}/proxy.conf;
    location ~ ^/health/(live|ready)$ {{ proxy_pass http://127.0.0.1:{port}; }}
    location ^~ /api/{role}/v1/ {{ proxy_pass http://127.0.0.1:{port}; }}
    location / {{ return 404; }}
}}
""")
    api = "https://" + domains[1]
    policy = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: blob: {api}; media-src 'self' blob: {api}; "
        f"connect-src 'self' {api}; font-src 'self' data:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    blocks.append(f"""server {{
    server_name {domains[0]};
{tls}
    root /opt/juya/rebuild/{environment}/admin-web;
    add_header Content-Security-Policy "{policy}" always;
    add_header Cache-Control $juya_admin_cache always;
    location /assets/ {{
        try_files $uri =404;
    }}
    location / {{
        try_files $uri $uri/ /index.html;
    }}
}}
server {{
    server_name {domains[3]};
{tls}
    default_type text/plain;
    charset utf-8;
    return 410 "请使用句芽英语微信小程序。\\n";
}}
""")
    return {"http.conf": HTTP, "proxy.conf": PROXY, environment + ".conf": "\n".join(blocks)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True, choices=["test", "production"])
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--includes", default="/etc/nginx/juya-rebuild")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    values = render(args.environment, args.certificate, args.key, args.includes)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, source in values.items():
        path = args.output / name
        if path.is_symlink() or (path.exists() and path.read_text() != source):
            raise ValueError("refusing to overwrite a different Nginx configuration")
        path.write_text(source, encoding="utf-8")
    print("Rendered HTTPS configuration; nginx -t is required before installation")


if __name__ == "__main__":
    main()
