"""Launch VoxWeaveTTS on the local Windows machine."""
import argparse
from .server import serve

def main() -> None:
    parser = argparse.ArgumentParser(description="VoxWeaveTTS local speech studio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.port)

if __name__ == "__main__":
    main()
