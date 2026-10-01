"""Serve the local browser tool. It never uploads source files."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

if __name__ == "__main__":
    directory = Path(__file__).resolve().parent / "docs"
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(directory)))
    address = f"http://127.0.0.1:{server.server_port}/"
    print("交付包工具已打开 / Delivery pack is ready: " + address)
    webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
