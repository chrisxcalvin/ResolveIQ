#!/bin/sh
# The Celery worker as its own free Render Web Service (separate from the
# API — see docs/checkpoints/phase-5.md for why: the worker alone needs
# ~287MB at runtime, which fits in one 512MB container but not alongside
# the API's own ~217MB in the same one).
#
# Render's free tier only exists for the "Web Service" type — its
# Background Worker product requires a paid plan. A Web Service must bind
# to $PORT and answer Render's health check, which a bare Celery worker
# doesn't do on its own, so this starts a one-line HTTP server in the
# background (any 200 response is enough) alongside the real worker.
set -e

echo "Starting minimal health endpoint on \$PORT=${PORT:-8000}..."
python -c "
import http.server, os, threading, time

class AlwaysOK(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'ok')

    def log_message(self, *args):
        pass  # don't spam the celery log with health-check hits

port = int(os.environ.get('PORT', 8000))
server = http.server.HTTPServer(('0.0.0.0', port), AlwaysOK)
threading.Thread(target=server.serve_forever, daemon=True).start()
while True:
    time.sleep(3600)
" &

echo "Starting Celery worker (foreground)..."
# Celery's default "prefork" pool spawns one child process per detected
# CPU core - on this container that was reporting 8, so the worker was
# actually running 8 full copies of the task pipeline at once, each with
# its own memory. --pool=solo (single process, no fork) is what Windows
# already forced locally for a different reason (prefork isn't supported
# there at all) - it turns out to matter here too, for real ticket volume
# this low, a single worker process is enough, and it keeps memory to the
# ~287MB measured in isolation instead of an 8x multiple of it.
exec celery -A app.worker worker --loglevel=info --pool=solo
