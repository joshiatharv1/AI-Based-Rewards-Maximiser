from pydantic_settings import BaseSettings
from typing import List
from pydantic import Field

class Settings(BaseSettings):
    # App
    APP_NAME: str = "Optivoy Rewards Engine"
    DEBUG: bool = True

    # RewardsCC API (get from RapidAPI - free tier)
    REWARDSCC_API_KEY: str = "YOUR_RAPIDAPI_KEY_HERE"
    REWARDSCC_BASE_URL: str = "https://rewards-credit-card-api.p.rapidapi.com"

    # Amadeus API (free sandbox at developers.amadeus.com)
    AMADEUS_CLIENT_ID: str = "YOUR_AMADEUS_CLIENT_ID_HERE"
    AMADEUS_CLIENT_SECRET: str = "YOUR_AMADEUS_CLIENT_SECRET_HERE"
    AMADEUS_BASE_URL: str = "https://test.api.amadeus.com"  # sandbox

    # OpenAI API Key (Keeps uppercase in code, reads lowercase from .env)
    OPENAI_API_KEY: str = Field(validation_alias="openai_api_key")

    # AWS Configuration (Keeps uppercase in code, reads lowercase from .env)
    AWS_REGION: str = Field(default="us-east-1", validation_alias="aws_region")

    aws_region: str = "us-east-1"

    CONNECT_API_KEY: str = ""

    # Valid credit card issuers (whitelist)
    APPROVED_ISSUERS: List[str] = [
        "American Express",
        "Chase",
        "Citi",
        "Capital One",
        "Barclays",
        "Wells Fargo",
        "Bank of America",
        "Discover",
        "US Bank",
    ]

    # Valid point denominations (fallback if API doesn't return them)
    DEFAULT_VALID_DENOMINATIONS: List[int] = [1000, 5000, 10000, 25000, 50000]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()