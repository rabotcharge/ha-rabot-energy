"""Constants for the Rabot Energy integration."""

from datetime import timedelta
from logging import Logger, getLogger

DOMAIN = "rabot_energy"
LOGGER: Logger = getLogger(__package__)

CONF_CONTRACT_NUMBER = "contract_number"

# The preview covers up to 72 hours and changes rarely, so polling often is wasteful.
UPDATE_INTERVAL = timedelta(minutes=30)

# The public Rabot API host. Users only change it for test environments.
# TODO: confirm the production host with the backend team before release.
DEFAULT_HOST = "https://api.rabot-charge.de"

# Entries created before the host became a setting were configured against this host.
# Only used by the version 1 to 2 migration.
LEGACY_HOST = "https://test-api.rabot-charge.de"
