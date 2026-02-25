"""Tests for Yahoo Finance symbol search."""

from unittest.mock import patch

import pytest

from app.services.yahoo.search import search

pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestSearch:
    @patch("app.services.yahoo.search._yq_search")
    async def test_delegates_to_yahooquery(self, mock_search):
        mock_search.return_value = {"quotes": [{"symbol": "AAPL"}]}

        result = await search("AAPL")

        mock_search.assert_called_once_with("AAPL")
        assert result == {"quotes": [{"symbol": "AAPL"}]}

    @patch("app.services.yahoo.search._yq_search")
    async def test_passes_kwargs(self, mock_search):
        mock_search.return_value = {"quotes": []}

        await search("AAPL", first_quote=False)

        mock_search.assert_called_once_with("AAPL", first_quote=False)

    @patch("app.services.yahoo.search._yq_search")
    async def test_returns_empty_on_no_results(self, mock_search):
        mock_search.return_value = {"quotes": []}

        result = await search("XYZXYZ")
        assert result["quotes"] == []
