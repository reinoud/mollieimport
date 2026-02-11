#!/usr/bin/env python3
"""Script to fetch and display all subscriptions from Mollie API.

This script retrieves all subscriptions across all customers from the Mollie API
and prints them as JSON to stdout.

Usage:
    python list_subscriptions.py [--config CONFIG] [--output OUTPUT]

Options:
    --config, -c    Path to config file (default: config.ini)
    --output, -o    Output file (default: stdout)
"""

import argparse
import json
import requests
import sys
import logging
from typing import List, Dict, Optional
from config_loader import load_config
from logger_setup import setup_logging


class MollieSubscriptionFetcher:
    """Fetches all subscriptions from Mollie API."""

    BASE_URL = "https://api.mollie.com/v2"

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        """Initialize the subscription fetcher.

        Args:
            api_key: Mollie API key for authentication
            logger: Optional logger instance
        """
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def _get_paginated(self, url: str) -> List[Dict]:
        """Fetch all items from a paginated endpoint.

        Args:
            url: The API endpoint URL

        Returns:
            List of all items from all pages

        Raises:
            RuntimeError: If API request fails
        """
        items = []
        next_url = url

        while next_url:
            try:
                self.logger.debug(f"Fetching: {next_url}")
                response = self.session.get(next_url, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Extract embedded items
                if "_embedded" in data and isinstance(data["_embedded"], dict):
                    # Find the collection key (usually the last path segment pluralized)
                    for key, value in data["_embedded"].items():
                        if isinstance(value, list):
                            items.extend(value)
                            self.logger.info(f"Retrieved {len(value)} items, total so far: {len(items)}")
                            break

                # Check for next page
                next_url = None
                if "_links" in data and "next" in data["_links"]:
                    next_link = data["_links"]["next"]
                    if isinstance(next_link, dict) and "href" in next_link:
                        next_url = next_link["href"]

            except requests.RequestException as e:
                self.logger.error(f"API request failed: {e}")
                raise RuntimeError(f"Failed to fetch data from {next_url}: {e}")

        return items

    def get_all_customers(self) -> List[Dict]:
        """Fetch all customers from Mollie.

        Returns:
            List of customer objects
        """
        self.logger.info("Fetching all customers...")
        url = f"{self.BASE_URL}/customers"
        customers = self._get_paginated(url)
        self.logger.info(f"Retrieved {len(customers)} customers")
        return customers

    def get_subscriptions_for_customer(self, customer_id: str) -> List[Dict]:
        """Fetch all subscriptions for a specific customer.

        Args:
            customer_id: Mollie customer ID

        Returns:
            List of subscription objects for this customer
        """
        self.logger.debug(f"Fetching subscriptions for customer {customer_id}")
        url = f"{self.BASE_URL}/customers/{customer_id}/subscriptions"
        try:
            subscriptions = self._get_paginated(url)
            if subscriptions:
                self.logger.info(f"Customer {customer_id}: found {len(subscriptions)} subscription(s)")
            return subscriptions
        except RuntimeError as e:
            self.logger.warning(f"Failed to fetch subscriptions for customer {customer_id}: {e}")
            return []

    def get_all_subscriptions(self) -> List[Dict]:
        """Fetch all subscriptions from all customers.

        Returns:
            List of all subscription objects with customer_id added to each
        """
        all_subscriptions = []
        customers = self.get_all_customers()

        for customer in customers:
            customer_id = customer.get("id")
            if not customer_id:
                self.logger.warning(f"Customer without ID found: {customer}")
                continue

            subscriptions = self.get_subscriptions_for_customer(customer_id)

            # Add customer information to each subscription for context
            for subscription in subscriptions:
                subscription["_customerInfo"] = {
                    "id": customer_id,
                    "name": customer.get("name"),
                    "email": customer.get("email")
                }

            all_subscriptions.extend(subscriptions)

        self.logger.info(f"Total subscriptions retrieved: {len(all_subscriptions)}")
        return all_subscriptions


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Fetch and display all Mollie subscriptions as JSON"
    )
    parser.add_argument(
        "--config", "-c",
        default="config.ini",
        help="Path to config file (default: config.ini)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file (default: stdout)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logger = setup_logging("list_subscriptions.log", level=log_level)

    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config = load_config(args.config)
        api_key = config.get("APIkey")

        if not api_key:
            logger.error("No API key found in configuration")
            sys.exit(1)

        # Fetch all subscriptions
        fetcher = MollieSubscriptionFetcher(api_key, logger)
        subscriptions = fetcher.get_all_subscriptions()

        # Prepare output
        output = {
            "total_count": len(subscriptions),
            "subscriptions": subscriptions
        }

        # Write to file or stdout
        if args.output:
            logger.info(f"Writing output to {args.output}")
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully wrote {len(subscriptions)} subscriptions to {args.output}")
        else:
            # Print to stdout
            print(json.dumps(output, indent=2, ensure_ascii=False))

    except FileNotFoundError as e:
        logger.error(f"Configuration file not found: {e}")
        sys.exit(1)
    except KeyError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        logger.error(f"Runtime error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

