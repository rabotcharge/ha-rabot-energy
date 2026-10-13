"""Constants for the Rabot Energy integration."""

from datetime import timedelta
from logging import Logger, getLogger

DOMAIN = "rabot_energy"
LOGGER: Logger = getLogger(__package__)

CONF_CONTRACT_NUMBER = "contract_number"

# The preview covers up to 72 hours and changes rarely, so polling often is wasteful.
UPDATE_INTERVAL = timedelta(minutes=30)

# Entries created before the host became a setting were configured against this host.
LEGACY_HOST = "https://test-api.rabot-charge.de"
