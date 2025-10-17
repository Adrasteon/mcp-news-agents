#!/usr/bin/env python3
"""Interactive helper to review news sources quickly."""

import argparse
import sys
from pathlib import Path
import webbrowser

from source_review_data import (
    CHOICE_TO_STATUS,
    DEFAULT_OUTPUT,
    STATUS_DESCRIPTIONS,
    build_result_row,
    fetch_sources,
    filter_sources,
    label_for,
    load_existing_results,
    write_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review news sources by opening each URL in a browser and logging the result."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to append results (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--start-id",
        type=int,
        help="Skip any sources with an id lower than this value.",
    )
    parser.add_argument(
        "--recheck",
        action="store_true",
        help="Re-review even if the source already has a logged result.",
    )
    parser.add_argument(
        "--reviewer",
        help="Optional reviewer name or initials to store with each result.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and list sources without opening a browser or writing results.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    all_sources = fetch_sources()
    existing_rows = load_existing_results(args.output)
    sources = filter_sources(all_sources, args.start_id, existing_rows, args.recheck)

    total = len(all_sources)
    pending = len(sources)
    options_text = ", ".join(
        f"[{key}] {STATUS_DESCRIPTIONS[val]}" for key, val in CHOICE_TO_STATUS.items() if val != "skip"
    )
    print(f"Loaded {total} sources. Reviewing {pending} this session.")
    print(f"Commands: {options_text}, [s] skip, [q] quit")

    for source in sources:
        source_id = source["id"]

        label = label_for(source)
        print("-" * 60)
        print(f"Source #{source_id}: {label}\nURL: {source['url']}")

        if args.dry_run:
            continue

        user_input = input("Press Enter to open in browser, or type 'skip' to move on: ").strip().lower()
        if user_input == "q":
            print("Stopping on user request.")
            break
        if user_input != "skip":
            webbrowser.open_new_tab(source["url"])

        while True:
            choice = input("Result [o/p/c/m/n/s/q]: ").strip().lower()
            if choice == "q":
                print("Stopping on user request.")
                return
            if choice in CHOICE_TO_STATUS:
                break
            print("Invalid choice. Use one of o, p, c, m, n, s, or q.")

        status_key = CHOICE_TO_STATUS[choice]
        if status_key == "skip":
            continue

        notes = input("Notes (optional, enter to skip): ").strip()
        row = build_result_row(
            source_id=source_id,
            label=label,
            url=source["url"],
            status=status_key,
            notes=notes,
            reviewer=args.reviewer or "",
        )
        write_result(args.output, row)
        existing_rows[source_id] = row
        print("Logged. Move to the next source when ready.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        sys.exit(1)
