# Alpaca API Implementation

This integration wires Alpaca's US API reference surface into ArbionTrader through a single authenticated Flask blueprint and a reusable Python client.

Source documentation: https://docs.alpaca.markets/us/reference/api-references

## What is implemented

The implementation is intentionally generic so Arbion does not need a new backend route every time Alpaca adds or renames a reference endpoint.

Implemented files:

- `utils/alpaca_api.py` — reusable Alpaca client with base URLs, auth headers, paper/sandbox mode, request validation, and JSON response normalization.
- `utils/alpaca_routes.py` — Flask API surface under `/api/alpaca`.
- `app.py` — registers `alpaca_bp` so the routes are live.

## Supported Alpaca API families

The backend supports the API families represented across Alpaca's API reference section from Authentication API through Broker API:

- Authentication API / OAuth token issuance
- Trading API
- Market Data API
- Broker API

## Environment variables

Set these in Heroku or your runtime environment.

### Trading API and Market Data API

```bash
ALPACA_API_KEY_ID=your_key_id
ALPACA_API_SECRET_KEY=your_secret_key
```

Supported aliases:

```bash
ALPACA_API_KEY=your_key_id
ALPACA_SECRET_KEY=your_secret_key
APCA_API_KEY_ID=your_key_id
APCA_API_SECRET_KEY=your_secret_key
```

### Broker API

```bash
ALPACA_BROKER_KEY=your_broker_key
ALPACA_BROKER_SECRET=your_broker_secret
```

If these are not provided, the client falls back to the Trading API key variables. Use dedicated Broker keys in production.

### OAuth / Authentication API

```bash
ALPACA_OAUTH_CLIENT_ID=your_client_id
ALPACA_OAUTH_CLIENT_SECRET=your_client_secret
ALPACA_ACCESS_TOKEN=optional_user_access_token
```

### Sandbox / paper mode

Any of these values will route supported calls to paper/sandbox endpoints:

```bash
ALPACA_PAPER=true
ALPACA_SANDBOX=true
ALPACA_ENV=sandbox
```

### Optional base URL overrides

Use only for testing or if Alpaca changes hostnames:

```bash
ALPACA_TRADING_BASE_URL=https://paper-api.alpaca.markets
ALPACA_MARKET_DATA_BASE_URL=https://data.alpaca.markets
ALPACA_BROKER_BASE_URL=https://broker-api.sandbox.alpaca.markets
ALPACA_AUTH_BASE_URL=https://authx.sandbox.alpaca.markets/v1
```

## Live Arbion endpoints

All routes require an authenticated Arbion user session.

### Integration status

```http
GET /api/alpaca/status
```

Returns supported domains, coverage notes, required env vars, and the generic proxy pattern.

### Authentication API

```http
POST /api/alpaca/auth/token
Content-Type: application/json

{
  "client_id": "optional_override",
  "client_secret": "optional_override"
}
```

If body values are omitted, Arbion uses `ALPACA_OAUTH_CLIENT_ID` and `ALPACA_OAUTH_CLIENT_SECRET`.

### Trading API convenience routes

```http
GET  /api/alpaca/trading/account
GET  /api/alpaca/trading/assets
GET  /api/alpaca/trading/orders
POST /api/alpaca/trading/orders
GET  /api/alpaca/trading/positions
```

### Market Data API convenience route

```http
GET /api/alpaca/market-data/stocks/AAPL/bars?timeframe=1Day&start=2025-01-01T00:00:00Z&end=2025-01-31T00:00:00Z
```

### Broker API convenience routes

```http
GET  /api/alpaca/broker/accounts
POST /api/alpaca/broker/accounts
```

## Generic proxy for every Alpaca REST subpage

Use the proxy for any documented REST endpoint that does not have a convenience route yet.

Pattern:

```http
/api/alpaca/proxy/<domain>/<alpaca-relative-path>
```

Domains:

- `auth`
- `trading`
- `market_data`
- `market-data`
- `broker`

Examples:

```http
GET /api/alpaca/proxy/trading/v2/account
GET /api/alpaca/proxy/trading/v2/assets
GET /api/alpaca/proxy/trading/v2/orders?status=open
POST /api/alpaca/proxy/trading/v2/orders
GET /api/alpaca/proxy/trading/v2/positions
GET /api/alpaca/proxy/market_data/v2/stocks/AAPL/bars?timeframe=1Day&start=2025-01-01T00:00:00Z
GET /api/alpaca/proxy/market_data/v1beta1/news?symbols=AAPL,MSFT
GET /api/alpaca/proxy/broker/v1/accounts
POST /api/alpaca/proxy/broker/v1/accounts
GET /api/alpaca/proxy/broker/v1/accounts/{account_id}
PATCH /api/alpaca/proxy/broker/v1/accounts/{account_id}
GET /api/alpaca/proxy/broker/v1/trading/accounts/{account_id}/account
GET /api/alpaca/proxy/broker/v1/trading/accounts/{account_id}/orders
POST /api/alpaca/proxy/broker/v1/trading/accounts/{account_id}/orders
GET /api/alpaca/proxy/broker/v1/trading/accounts/{account_id}/positions
GET /api/alpaca/proxy/broker/v1/assets
GET /api/alpaca/proxy/broker/v1/calendar
GET /api/alpaca/proxy/broker/v1/clock
```

## Response shape

Every client response is normalized:

```json
{
  "success": true,
  "status_code": 200,
  "url": "https://paper-api.alpaca.markets/v2/account",
  "data": {},
  "error": null
}
```

Failed calls return:

```json
{
  "success": false,
  "status_code": 400,
  "url": "https://...",
  "data": null,
  "error": {}
}
```

## Security constraints

The proxy is controlled, not open-ended:

- Only Alpaca domains are allowed.
- Only relative paths are accepted.
- Full URLs are rejected.
- Path traversal is rejected.
- Only `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` are allowed.
- Routes require `login_required`.
- Broker API uses Basic auth from broker keys.
- Trading/Market Data use Alpaca key headers unless `ALPACA_ACCESS_TOKEN` is supplied.

## Important production note

This gives Arbion backend coverage for Alpaca's REST reference surface. It does not automatically create polished frontend screens for every single Alpaca subpage. For production UX, build specific UI flows on top of these backend endpoints for:

- account connection/testing
- account overview
- market data viewer
- order ticket
- positions table
- broker account onboarding
- funding/transfers
- broker trading controls
- broker account activity/events

## Smoke test checklist

After deployment:

1. Add required Alpaca env vars in Heroku.
2. Log in to Arbion.
3. Call `GET /api/alpaca/status`.
4. Call `GET /api/alpaca/trading/account` using paper credentials first.
5. Call one market data endpoint.
6. If Broker API is enabled, call `GET /api/alpaca/broker/accounts` in sandbox first.
7. Only after sandbox verification, enable live credentials.

## Cursor/Codex next steps

Paste this task into Codex if you want UI work next:

```text
Build a professional Alpaca integration UI in ArbionTrader using the existing Flask endpoints under /api/alpaca. Add a settings/test-connection panel, account overview, market data query panel, orders panel, positions table, and Broker API sandbox account list. Use the generic proxy only from server-side approved UI actions. Never expose Alpaca secrets to the frontend. Show exact API error messages in the UI.
```
