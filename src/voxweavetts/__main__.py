"""Launch the loopback development preview server."""
import argparse
from .server import serve

def main() -> None:
    parser = argparse.ArgumentParser(description="VoxWeaveTTS development preview")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.port)

if __name__ == "__main__":
    main()
