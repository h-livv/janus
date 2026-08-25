from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transport.interface import Transport


def main():
    transport = Transport()
    transport.load_topology()
    transport.run()


if __name__ == "__main__":
    main()
