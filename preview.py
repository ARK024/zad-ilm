#!/usr/bin/env python3
import http.server
import socketserver
import os
import sys

PORT = 8085
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

if __name__ == '__main__':
    os.chdir(DIRECTORY)
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"==================================================")
        print(f" 🌿 زاد العلم — خادم المعاينة المباشر (Preview)")
        print(f" افتح المتصفح على الرابط:")
        print(f" http://localhost:{PORT}/frontend/index.html")
        print(f" لمعاينة الودجت العائم:")
        print(f" http://localhost:{PORT}/frontend/widget.html")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nتم إيقاف الخادم.")
