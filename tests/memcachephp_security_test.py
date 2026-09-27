"""Exercise MemcachePHP security behavior against disposable Docker containers."""

import base64
import http.cookiejar
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


suffix = uuid.uuid4().hex[:10]
image = f"memcachephp-security-test:{suffix}"
network = f"memcachephp-security-{suffix}"
cache_container = f"memcachephp-security-cache-{suffix}"
web_container = f"memcachephp-security-web-{suffix}"


def docker(*args):
    return subprocess.run(["docker", *args], check=True, capture_output=True, text=True).stdout.strip()


def memcache(port, command):
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(command)
        connection.shutdown(socket.SHUT_WR)
        response = bytearray()
        while True:
            chunk = connection.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
    return bytes(response)


def set_key(port, key, value):
    command = b"set " + key + b" 0 0 " + str(len(value)).encode() + b"\r\n" + value + b"\r\n"
    assert b"STORED\r\n" in memcache(port, command)


def key_exists(port, key):
    return b"VALUE " + key + b" " in memcache(port, b"get " + key + b"\r\n")


def request(opener, url, auth=True, data=None, extra_headers=None):
    headers = dict(extra_headers or {})
    if auth:
        credentials = base64.b64encode(b"securitytest:test-only-password").decode()
        headers["Authorization"] = "Basic " + credentials
    payload = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        response = opener.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.read().decode("utf-8", errors="replace")


def expect_status(actual, expected):
    assert actual == expected, f"expected HTTP {expected}, got {actual}"


try:
    docker("build", "-q", "-f", "Dockerfile-memcachephp", "-t", image, ".")
    docker("network", "create", network)
    docker("run", "-d", "--name", cache_container, "--network", network,
           "-p", "127.0.0.1::11211", "memcached:alpine", "-m", "16")
    docker("run", "-d", "--name", web_container, "--network", network,
           "-p", "127.0.0.1::80", "-e", "MEMCACHEPHP_ADMIN_USER=securitytest",
           "-e", "MEMCACHEPHP_ADMIN_PASS=test-only-password",
           "-e", f"MEMCACHEPHP_SERVERS={cache_container}:11211", image)
    cache_port = int(docker("port", cache_container, "11211/tcp").rsplit(":", 1)[1])
    web_port = int(docker("port", web_container, "80/tcp").rsplit(":", 1)[1])
    base = f"http://127.0.0.1:{web_port}/index.php"
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    outsider = urllib.request.build_opener()

    for _ in range(30):
        try:
            if request(opener, base, auth=False)[0] == 401:
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(0.25)
    else:
        raise AssertionError("MemcachePHP did not start")
    time.sleep(1)

    expect_status(request(opener, base, auth=False)[0], 401)
    status, page = request(opener, base)
    expect_status(status, 200)
    token_match = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', page)
    assert token_match, "flush form has no CSRF token"
    token = token_match.group(1)
    assert 'method="post"' in page and 'op=6' in page

    key = b"xss-test"
    xss_value = b'<img src=x onerror=alert(1)>'
    set_key(cache_port, key, xss_value)
    key_param = base64.b64encode(key).decode()
    item_url = base + "?" + urllib.parse.urlencode({"op": 4, "server": 0, "key": key_param})
    status, page = request(opener, item_url)
    expect_status(status, 200)
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "<img src=x onerror=alert(1)>" not in page
    assert 'method="post"' in page and 'op=5' in page

    html_key = b"<svg/onload=alert(1)>"
    set_key(cache_port, html_key, b"safe-value")
    html_key_url = base + "?" + urllib.parse.urlencode({
        "op": 4, "server": 0, "key": base64.b64encode(html_key).decode()})
    status, page = request(opener, html_key_url)
    expect_status(status, 200)
    assert "&lt;svg/onload=alert(1)&gt;" in page
    assert "<svg/onload=alert(1)>" not in page

    delete_url = base + "?op=5"
    flush_url = base + "?op=6"
    expect_status(request(opener, delete_url + "&server=0&key=" + key_param)[0], 405)
    expect_status(request(opener, flush_url + "&server=0")[0], 405)
    assert key_exists(cache_port, key)
    delete_data = {"server": 0, "key": key_param}
    expect_status(request(opener, delete_url, data=delete_data)[0], 403)
    expect_status(request(opener, delete_url, data={**delete_data, "csrf_token": "invalid"})[0], 403)
    expect_status(request(outsider, delete_url, data={**delete_data, "csrf_token": token})[0], 403)
    assert key_exists(cache_port, key)

    crlf = base64.b64encode(b"xss-test\r\nflush_all").decode()
    expect_status(request(opener, base + "?" + urllib.parse.urlencode(
        {"op": 4, "server": 0, "key": crlf}))[0], 400)
    expect_status(request(opener, delete_url, data={"server": 0, "key": crlf,
                                                    "csrf_token": token})[0], 400)
    expect_status(request(opener, delete_url, data={**delete_data, "server": 99,
                                                    "csrf_token": token})[0], 400)
    assert key_exists(cache_port, key)

    expect_status(request(opener, delete_url, data={**delete_data, "csrf_token": token})[0], 200)
    assert not key_exists(cache_port, key)
    set_key(cache_port, b"flush-test", b"still-here")
    expect_status(request(opener, flush_url, data={"server": 0})[0], 403)
    assert key_exists(cache_port, b"flush-test")
    expect_status(request(opener, flush_url,
                          data={"server": 0, "csrf_token": token})[0], 200)
    assert not key_exists(cache_port, b"flush-test")

    status, prefixed_page = request(opener, base,
                                    extra_headers={"X-Forwarded-Prefix": "/memcacheui"})
    expect_status(status, 200)
    assert 'action="/memcacheui/index.php?op=6"' in prefixed_page
    print("MemcachePHP security integration test passed")
finally:
    for container in (web_container, cache_container):
        subprocess.run(["docker", "rm", "-f", container], capture_output=True)
    subprocess.run(["docker", "network", "rm", network], capture_output=True)
    subprocess.run(["docker", "image", "rm", image], capture_output=True)
