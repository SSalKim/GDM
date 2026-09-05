"""Compatibility entry point for Cloudflare's existing fetch workflow."""

from scripts.collect_weatherlab import main


if __name__ == "__main__":
    raise SystemExit(main())
