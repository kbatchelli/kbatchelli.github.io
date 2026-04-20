#!/usr/bin/env python3
"""Dev server. Builds the site and serves it locally."""

import http.server
import os
import subprocess
import sys

PORT = 8000

def main():
    subprocess.run([sys.executable, "build.py"], check=True)
    os.chdir("_site")
    handler = http.server.SimpleHTTPRequestHandler
    with http.server.HTTPServer(("", PORT), handler) as server:
        print(f"Serving at http://localhost:{PORT}")
        server.serve_forever()

if __name__ == "__main__":
    main()
