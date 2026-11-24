"""Constants for the Rabot Energy client."""

# Price time series for the token's contract; the optional `contractNumber` query parameter
# must match it.
# The service host is not a constant: it differs per environment (local, test, production)
# and is passed to `Auth` by the caller.
PRICES_PATH = "/api/home-assistant-service/v1/energy-prices/average"

DEFAULT_TIMEOUT = 15  # seconds
