# Rabot Energy for Home Assistant

Shows your Rabot Energy electricity price preview (up to 72 hours ahead) in Home Assistant, for
one contract per entry. Early scaffold built on the service endpoint
`GET /api/home-assistant-service/v1/energy-prices/average?contractNumber=...` (see "Known gaps").

## What you get

One device per contract with these sensors (unit `EUR/kWh`):

| Sensor | Meaning |
| --- | --- |
| Current price | Gross price of the slot that contains "now" |
| Current price (net) | Net price of the current slot, when the API sends it |
| Next price | Gross price of the next slot |
| Lowest upcoming price | Cheapest current-or-later slot; attributes `start`, `end` |
| Highest upcoming price | Most expensive current-or-later slot; attributes `start`, `end` |

The API sends prices in cent per kWh with one `moment` per record; the integration converts them to
EUR/kWh and derives each slot's end from the next record. The current price follows the slot
boundaries from cached data, without another API call. The service is polled every 30 minutes.

The *Current price* sensor can be chosen in the Energy dashboard under "Use an entity with current
price".

## Setup

1. Get your **contract number** in the Rabot app, plus a long-lived **access token** if the server
   you use needs one. You also need the **server address** of the Rabot service (for example
   `http://10.0.0.5:8012`).
2. Add this repository to HACS as a custom repository (category *Integration*), install it and
   restart Home Assistant.
3. Settings > Devices & services > Add integration > *Rabot Energy*, then enter the server address,
   the contract number and, if needed, the token.

To switch environments later (local, test, production) use **Reconfigure** in the three-dot menu
of the entry; no need to delete it. An empty token field keeps the stored token.

If the token is revoked or expires, Home Assistant asks for a new one (reauthentication).

## Design

- API code lives in the `_lib` package (a copy of the separate `rabot-energy` library, repo
  `python-rabot-energy`). It is bundled here until the library is published on PyPI, which Home
  Assistant Core requires. The library mirrors the API and converts nothing.
- All conversion and derived values live in `custom_components/rabot_energy/prices.py`, which has no
  Home Assistant imports and is unit-tested on its own.
- The config entry stores the server address, the contract number and the optional token. The
  address is a setting, not a constant, because it differs per environment.

## Known gaps

- The response has one `moment` per record and no slot length. The integration derives it from the
  spacing of the records (15 minutes in the samples) and assumes one hour only when there is a single
  record (`prices.py`).
- `moment` has no time zone (`2026-10-13 07:30`). The integration reads it as **UTC**; the data
  supports that (a day's last record is `21:45`, which is 23:45 Berlin time). To be confirmed with the
  backend team; the only place to change is `_parse_moment` in `prices.py`.
- The sample request sends no token, so the token is optional. Bearer auth was confirmed against the
  earlier test API only. The public service will probably need a token.
- It is unclear what "net" means: net was about 17 ct while gross was about 41.5 ct, far below
  gross / 1.19. The "Current price (net)" sensor may mislead until this is clarified.
- `priceCap` (null in the samples) and the base provider working price are parsed by the library but
  not exposed as sensors yet.
- The contract number format is not validated by the config flow.
- Prices are assumed to be in EUR (the schema only says cent).
- The library is bundled under `_lib` because `rabot-energy` is not on PyPI yet. Before a Home
  Assistant Core submission it must be published and this copy removed.
- No config-flow tests yet (they need `pytest-homeassistant-custom-component`, which needs the
  Python version of the current Home Assistant release), no diagnostics, no `get_prices` action,
  no logo image (only the icon is in `custom_components/rabot_energy/brand/`).
- `codeowners` in `manifest.json` is empty and the repository URLs are placeholders.

## Development

```shell
pip install -r requirements_test.txt
pytest          # price logic tests, no Home Assistant needed
```

## Licence

Apache-2.0
