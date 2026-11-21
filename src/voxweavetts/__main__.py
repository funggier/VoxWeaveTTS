"""Launch VoxWeaveTTS with the Portable listener settings."""
import argparse

from .network import load_network_settings
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="VoxWeaveTTS speech studio")
    parser.add_argument("--host", help="IPv4 address to listen on")
    parser.add_argument("--port", type=int, help="TCP port to listen on")
    args = parser.parse_args()
    try:
        settings = load_network_settings(args.host, args.port)
        serve(settings.port, host=settings.host, access_code=settings.access_code)
    except (ValueError, OSError) as error:
        parser.exit(1, f"VoxWeaveTTS: {error}\n")


if __name__ == "__main__":
    main()
