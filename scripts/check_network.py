"""Find out which internet address this computer cannot reach.  python scripts/check_network.py"""
import socket
import sys
import urllib.request

HOSTS = {
    "generativelanguage.googleapis.com": "Gemini API (the audit's AI steps)",
    "huggingface.co": "Whisper + embedding model downloads (first run only)",
    "cdn-lfs.huggingface.co": "model file downloads (first run only)",
    "speech.platform.bing.com": "edge-tts voices (audio generation)",
    "pypi.org": "pip installs",
}


def main() -> int:
    bad = 0
    for host, why in HOSTS.items():
        try:
            ip = socket.gethostbyname(host)
        except OSError as e:
            print(f"[FAIL] {host:<38} DNS lookup failed ({e})  <- needed for: {why}")
            bad += 1
            continue
        try:
            urllib.request.urlopen(f"https://{host}", timeout=8)
            print(f"[ OK ] {host:<38} {ip}  ({why})")
        except urllib.error.HTTPError:
            print(f"[ OK ] {host:<38} {ip}  reachable ({why})")  # an HTTP error page still means the network works
        except Exception as e:  # noqa: BLE001
            print(f"[FAIL] {host:<38} resolved to {ip} but the connection failed ({str(e)[:70]})  <- {why}")
            bad += 1
    if bad:
        print("\nFix: reconnect Wi-Fi, disable VPN/proxy, or try a mobile hotspot (college/office networks often block these).\n"
              "If DNS fails on every host, set DNS to 8.8.8.8 and 1.1.1.1 in Windows: Settings > Network > your connection > DNS server assignment.")
    else:
        print("\nAll addresses reachable.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
