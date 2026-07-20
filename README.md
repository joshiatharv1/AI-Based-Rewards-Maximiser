# Optivoy Rewards Engine

Agentic loyalty rewards booking system — interview task for Optivoy.ai.

## What This Does
1. Fetches a user's credit cards and points balances (mock bank API)
2. Validates cards against approved issuer whitelist
3. Searches hotels via Amadeus API
4. Fetches dynamic transfer ratios from RewardsCC API
5. Validates point denominations (must be fixed: 1000, 5000, 10000...)
6. Converts card points → hotel loyalty points
7. Calculates full payment breakdown (room + tax + fees + points discount + cash)
8. Agent recommends top 3 redemption options across all user cards

## Edge Cases Covered
| # | Edge Case | Implementation |
|---|-----------|---------------|
| 1 | Fixed denominations only | `card_service.validate_denomination()` |
| 2 | Verified card issuer | `card_service.validate_card()` + approved whitelist |
| 3 | Dynamic conversion ratio | `rewardscc_service.get_transfer_partners()` |
| 4 | Full payment breakdown | `conversion_engine.build_payment_breakdown()` |
| 5 | Approved card required | Validation before every booking step |

## Setup

### 1. Clone and install
```bash
cd optivoy
pip install -r requirements.txt
```

### 2. Configure API keys
```bash
cp .env.example .env
# Edit .env and add your keys
```

**RewardsCC** (free tier):
- Go to https://rapidapi.com/rewardsccapi/api/rewards-credit-card-api
- Sign up (no card needed)
- Subscribe to free tier
- Copy API key → `REWARDSCC_API_KEY`

**Amadeus** (free sandbox):
- Go to https://developers.amadeus.com
- Sign up (no card needed)
- Create new app
- Copy Client ID + Secret → `AMADEUS_CLIENT_ID`, `AMADEUS_CLIENT_SECRET`

> **No keys? No problem.** The app runs fully on mock data without any API keys.

### 3. Run Day 1 tests
```bash
python test_day1.py
```

### 4. Start the server
```bash
uvicorn app.main:app --reload
```
Visit http://localhost:8000/docs for interactive API docs.

## Project Structure
```
optivoy/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── core/
│   │   └── config.py            # Settings and environment
│   ├── models/
│   │   └── schemas.py           # All Pydantic models
│   ├── services/
│   │   ├── card_service.py      # Mock bank API
│   │   ├── rewardscc_service.py # RewardsCC API client
│   │   ├── amadeus_service.py   # Amadeus hotel API client
│   │   └── conversion_engine.py # Points math engine
│   ├── agents/                  # LangGraph agent (Day 3)
│   └── api/routes/
│       ├── cards.py
│       ├── hotels.py
│       ├── conversion.py
│       └── booking.py
├── test_day1.py                 # End-to-end Day 1 tests
├── requirements.txt
└── .env.example
```

## Day-by-Day Plan
| Day | Focus |
|-----|-------|
| ✅ Day 1 | FastAPI skeleton, mock bank API, RewardsCC + Amadeus integration |
| Day 2 | Conversion engine refinement, all edge case guards |
| Day 3 | LangGraph agent skeleton, hotel search integration |
| Day 4 | Top 3 ranking logic, agent reasoning output |
| Day 5 | End-to-end testing, AWS Secrets Manager, architecture diagram |