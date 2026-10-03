from http.server import BaseHTTPRequestHandler

from showcase.server import Handler as ShowcaseHandler


class handler(BaseHTTPRequestHandler):
    send_bytes = ShowcaseHandler.send_bytes
    do_GET = ShowcaseHandler.do_GET