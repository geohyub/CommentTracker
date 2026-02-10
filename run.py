#!/usr/bin/env python3
"""Entry point for Comment Tracker web application."""

import argparse
import webbrowser
from comment_tracker.app import create_app


def main():
    parser = argparse.ArgumentParser(description="Comment Tracker & Analytics")
    parser.add_argument("--port", type=int, default=5000, help="Port to run on (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--db", default=None, help="Database file path (default: ~/.comment-tracker/comments.db)")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    args = parser.parse_args()

    app = create_app(db_path=args.db)

    if not args.no_browser and not args.debug:
        webbrowser.open(f"http://{args.host}:{args.port}")

    print(f"\n  Comment Tracker & Analytics v1.0.0")
    print(f"  Running at: http://{args.host}:{args.port}")
    print(f"  Database: {args.db or '~/.comment-tracker/comments.db'}")
    print(f"  Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
