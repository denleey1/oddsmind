#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
URL Configuration for Scrapers

This file centralizes all the URLs used by the scraping modules.
By managing URLs here, we can easily update them without changing the scraper logic.
"""

# Base domains for different services
BASE_URLS = {
    "titan007_main": "https://zq.titan007.com",
    "titan007_odds": "https://1x2d.titan007.com",
    "titan007_data": "https://data.titan007.com",
}

# A structured dictionary for API endpoints
# This allows adding more metadata in the future, e.g., headers, method, etc.
API_ENDPOINTS = {
    # Endpoint for fetching odds data for a single match
    "match_odds": {
        "url_template": f"{BASE_URLS['titan007_odds']}/{{match_id}}.js",
        "description": "JS interface for single match odds data."
    },

    # Endpoint for fetching match results for a league in a specific season
    "league_results": {
        "url_template": f"{BASE_URLS['titan007_main']}/jsData/matchResult/{{season}}/{{league_filename}}",
        "description": "JS interface for league match results."
    },

    # Endpoint for fetching league standings/tables
    "league_standings": {
        "url_template": f"{BASE_URLS['titan007_main']}/jsData/standings/{{season}}/s{{league_id}}.js",
        "description": "JS interface for league standings."
    },
    
    # Endpoint for fetching all company names
    "all_companies": {
        "url_template": f"{BASE_URLS['titan007_data']}/jsData/gamecompany/allCompany.js",
        "description": "JS interface for a list of all betting companies."
    },

    # Endpoint for Asian handicap odds page
    "asian_handicap": {
        "url_template": "https://vip.titan007.com/AsianOdds_n.aspx?id={match_id}",
        "description": "Asian handicap odds page for a single match."
    },
}

def get_url(endpoint_name: str, **kwargs) -> str:
    """
    Generates a URL for a given endpoint name using provided keyword arguments.

    Args:
        endpoint_name: The key of the endpoint in the API_ENDPOINTS dictionary.
        **kwargs: The parameters to format the URL template (e.g., match_id, league_id).

    Returns:
        The formatted URL string.

    Raises:
        KeyError: If the endpoint_name is not found.
    """
    try:
        template = API_ENDPOINTS[endpoint_name]["url_template"]
        return template.format(**kwargs)
    except KeyError:
        raise KeyError(f"Endpoint '{endpoint_name}' not found in URL configuration.")
    except Exception as e:
        raise ValueError(f"Error formatting URL for endpoint '{endpoint_name}': {e}")