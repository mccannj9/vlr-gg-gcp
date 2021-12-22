#! /usr/bin/env python

import argparse

from valorant_scraper_gcp.scraper import ValorantResults

if __name__ == "__main__":

    desc = """ x """

    parser = argparse.ArgumentParser(
        prog='load-db-and-tables.py', description=desc
    )

    parser.add_argument(
        "--sqlite-path", type=str, required=True,
        help="Path to sqlite database for wine reviews dumps"
    )

    parser.add_argument(
        "--scrape-delay", type=int, required=False, default=1,
        help="Time to delay requests for scraping"
    )

    args = parser.parse_args()

    results_scraper = ValorantResults(args.sqlite_path, args.scrape_delay)

    results_scraper.update_matches_database()