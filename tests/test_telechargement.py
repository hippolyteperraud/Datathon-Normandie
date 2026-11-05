"""Téléchargement : un serveur lent ne doit jamais bloquer le moteur (incident du 25/10/2026)."""
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from prairimetre import telecharger


class GoutteAGoutte(BaseHTTPRequestHandler):
    """Envoie un octet toutes les 0,2 s pendant 10 s : jamais silencieux, jamais fini."""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "50")
        self.end_headers()
        try:
            for _ in range(50):
                self.wfile.write(b"x")
                self.wfile.flush()
                threading.Event().wait(0.2)  # pas time.sleep, neutralisé dans le test
        except OSError:  # le client a abandonné : c'est ce qu'on attend
            pass

    def log_message(self, *args):
        pass


class Delais(unittest.TestCase):
    def setUp(self):
        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), GoutteAGoutte)
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.serveur.server_port}/"

    def tearDown(self):
        self.serveur.shutdown()
        self.serveur.server_close()

    def test_duree_totale_bornee(self):
        debut = time.monotonic()
        with mock.patch.object(telecharger.time, "sleep"):  # pas d'attente entre les essais
            with self.assertRaises(telecharger.DelaiDepasse):
                telecharger._get(self.url, duree_max=1, timeout=5)
        self.assertLess(time.monotonic() - debut, 4 * 1.5 + 2)  # 4 essais d'environ 1 s


if __name__ == "__main__":
    unittest.main()
