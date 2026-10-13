"""Constants for the Rabot Energy client."""

# Price time series for one contract; the contract goes in the `contractNumber` query parameter.
# The service host is not a constant: it differs per environment (local, test, production)
# and is passed to `Auth` by the caller.
PRICES_PATH = "/api/home-assistant-service/v1/energy-prices/average"

DEFAULT_TIMEOUT = 15  # seconds
