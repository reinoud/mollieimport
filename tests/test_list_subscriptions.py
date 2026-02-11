"""Tests for list_subscriptions.py functionality."""

import pytest
from unittest.mock import Mock, patch
from list_subscriptions import MollieSubscriptionFetcher


class TestMollieSubscriptionFetcher:
    """Test the MollieSubscriptionFetcher class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return Mock()

    @pytest.fixture
    def fetcher(self, mock_logger):
        """Create a MollieSubscriptionFetcher instance."""
        return MollieSubscriptionFetcher("test_api_key_12345", mock_logger)

    def test_initialization(self, fetcher):
        """Test that fetcher initializes correctly."""
        assert fetcher.api_key == "test_api_key_12345"
        assert fetcher.BASE_URL == "https://api.mollie.com/v2"
        assert "Authorization" in fetcher.session.headers
        assert fetcher.session.headers["Authorization"] == "Bearer test_api_key_12345"

    def test_get_paginated_single_page(self, fetcher, mock_logger):
        """Test fetching from a single-page response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "_embedded": {
                "customers": [
                    {"id": "cst_1", "name": "Customer 1"},
                    {"id": "cst_2", "name": "Customer 2"}
                ]
            },
            "_links": {}
        }

        with patch.object(fetcher.session, "get", return_value=mock_response):
            result = fetcher._get_paginated("https://api.mollie.com/v2/customers")

        assert len(result) == 2
        assert result[0]["id"] == "cst_1"
        assert result[1]["id"] == "cst_2"

    def test_get_paginated_multiple_pages(self, fetcher, mock_logger):
        """Test fetching from multiple pages."""
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "_embedded": {
                "customers": [
                    {"id": "cst_1", "name": "Customer 1"}
                ]
            },
            "_links": {
                "next": {"href": "https://api.mollie.com/v2/customers?from=cst_2"}
            }
        }

        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "_embedded": {
                "customers": [
                    {"id": "cst_2", "name": "Customer 2"}
                ]
            },
            "_links": {}
        }

        with patch.object(fetcher.session, "get", side_effect=[mock_response_1, mock_response_2]):
            result = fetcher._get_paginated("https://api.mollie.com/v2/customers")

        assert len(result) == 2
        assert result[0]["id"] == "cst_1"
        assert result[1]["id"] == "cst_2"

    def test_get_all_customers(self, fetcher, mock_logger):
        """Test getting all customers."""
        mock_customers = [
            {"id": "cst_1", "email": "customer1@example.com"},
            {"id": "cst_2", "email": "customer2@example.com"}
        ]

        with patch.object(fetcher, "_get_paginated", return_value=mock_customers):
            result = fetcher.get_all_customers()

        assert len(result) == 2
        assert result == mock_customers

    def test_get_subscriptions_for_customer(self, fetcher, mock_logger):
        """Test getting subscriptions for a specific customer."""
        mock_subscriptions = [
            {"id": "sub_1", "status": "active"},
            {"id": "sub_2", "status": "active"}
        ]

        with patch.object(fetcher, "_get_paginated", return_value=mock_subscriptions):
            result = fetcher.get_subscriptions_for_customer("cst_12345")

        assert len(result) == 2
        assert result == mock_subscriptions

    def test_get_subscriptions_for_customer_handles_errors(self, fetcher, mock_logger):
        """Test that errors fetching subscriptions are handled gracefully."""
        with patch.object(fetcher, "_get_paginated", side_effect=RuntimeError("API error")):
            result = fetcher.get_subscriptions_for_customer("cst_12345")

        assert result == []
        mock_logger.warning.assert_called()

    def test_get_all_subscriptions(self, fetcher, mock_logger):
        """Test getting all subscriptions from all customers."""
        mock_customers = [
            {"id": "cst_1", "name": "Customer 1", "email": "c1@example.com"},
            {"id": "cst_2", "name": "Customer 2", "email": "c2@example.com"}
        ]

        mock_subs_1 = [{"id": "sub_1", "status": "active"}]
        mock_subs_2 = [{"id": "sub_2", "status": "active"}]

        with patch.object(fetcher, "get_all_customers", return_value=mock_customers):
            with patch.object(fetcher, "get_subscriptions_for_customer", side_effect=[mock_subs_1, mock_subs_2]):
                result = fetcher.get_all_subscriptions()

        assert len(result) == 2
        assert result[0]["id"] == "sub_1"
        assert result[0]["_customerInfo"]["id"] == "cst_1"
        assert result[0]["_customerInfo"]["name"] == "Customer 1"
        assert result[1]["id"] == "sub_2"
        assert result[1]["_customerInfo"]["id"] == "cst_2"

    def test_get_all_subscriptions_skips_customers_without_id(self, fetcher, mock_logger):
        """Test that customers without ID are skipped."""
        mock_customers = [
            {"name": "Customer 1", "email": "c1@example.com"},  # No ID
            {"id": "cst_2", "name": "Customer 2", "email": "c2@example.com"}
        ]

        mock_subs = [{"id": "sub_2", "status": "active"}]

        with patch.object(fetcher, "get_all_customers", return_value=mock_customers):
            with patch.object(fetcher, "get_subscriptions_for_customer", return_value=mock_subs):
                result = fetcher.get_all_subscriptions()

        # Only customer 2's subscription should be returned
        assert len(result) == 1
        assert result[0]["_customerInfo"]["id"] == "cst_2"
        mock_logger.warning.assert_called()

