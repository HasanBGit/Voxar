"""Call a running `voxar serve` over HTTP using only the standard library.

    uv run voxar serve &                                  # in another terminal
    uv run python examples/04_http_client.py sample.wav

Shows the one thing a real client must do: when the server is busy it answers 503 with a
Retry-After header, and the client should wait and try again.
"""

import json
import sys
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8765"


def post(path: str, body: bytes, content_type: str, attempts: int = 5) -> bytes:
    request = urllib.request.Request(URL + path, data=body, headers={"Content-Type": content_type})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code != 503 or attempt == attempts - 1:
                raise SystemExit(f"error {error.code}: {error.read().decode()}") from None
            time.sleep(float(error.headers.get("Retry-After", "1")))  # busy: back off, retry
    raise AssertionError("unreachable")


def main(path: str) -> None:
    with open(path, "rb") as handle:
        reply = post("/v1/transcribe", handle.read(), "audio/wav")
    print(json.loads(reply)["text"])


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
