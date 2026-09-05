"""Manual collection entry point; use --start and --end for historical cycles."""

from scripts.collect_weatherlab import main


if __name__ == "__main__":
    raise SystemExit(main())
