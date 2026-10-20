# Rabot Energy for Home Assistant

Shows your Rabot Energy electricity price preview (up to 72 hours ahead) in Home Assistant, for
one contract per entry. Built on the service endpoint
`GET /api/home-assistant-service/v1/energy-prices/average?contractNumber=...` (see "Known gaps").

## What you get

One device per contract with these sensors (unit `EUR/kWh`):

| Sensor | Meaning |
| --- | --- |
| Current price | Gross price of the slot that contains "now"; attribute `prices` holds the whole preview |
| Next price | Gross price of the next slot |
| Lowest upcoming price | Cheapest current-or-later slot; attributes `start`, `end` |
| Highest upcoming price | Most expensive current-or-later slot; attributes `start`, `end` |

The API sends gross prices only, in cent per kWh, with one `moment` per record; the integration
converts them to EUR/kWh and derives each slot's end from the next record. The current price follows
the slot boundaries from cached data, without another API call. The service is polled every
30 minutes.

## Setup

### 1. Before you start

You need:

- **Home Assistant 2026.3.0 or newer.**
- **HACS** installed ([hacs.xyz/docs/use](https://hacs.xyz/docs/use/)), or access to the
  `config` folder for a manual install.
- Your **contract number**, shown in the Rabot app.
- The **server address** of the Rabot service, including the scheme and, if needed, the port (for
  example `https://api.example.com` or `http://10.0.0.5:8012`). It must be reachable from Home
  Assistant.
- An **access token**, only if the server needs one: a long-lived token created in the Rabot app.

### 2. Install the integration

**With HACS (recommended)**

[![Open in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=rabotcharge&repository=ha-rabot-energy&category=integration)

Or by hand:

1. HACS > three-dot menu (top right) > *Custom repositories*.
2. Repository `https://github.com/rabotcharge/ha-rabot-energy`, type *Integration* > *Add*.
3. Search HACS for **Rabot Energy** > *Download*.
4. Restart Home Assistant (Settings > System > three-dot menu > *Restart Home Assistant*).

**Manually**

1. Download the repository (*Code* > *Download ZIP*, or the ZIP of the newest tag) and copy `custom_components/rabot_energy` into the
   `custom_components` folder of your Home Assistant `config` folder (create it if missing).
2. Restart Home Assistant.

### 3. Add your contract

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rabot_energy)

Or: Settings > Devices & services > *Add integration* > search **Rabot Energy**. Then fill in:

| Field | Value |
| --- | --- |
| Server address | Full address with `http://` or `https://`, without a trailing path |
| Contract number | As shown in the Rabot app |
| Access token (optional) | Leave empty if the server needs none |

The integration tests the settings with one request before saving. On success you get a device
*Rabot &lt;contract number&gt;* with the four sensors. Repeat this step for every further contract.

### 4. Use the price in the Energy dashboard (optional)

Settings > Dashboards > *Energy* > *Electricity grid* > edit your grid consumption > *Use an entity
with current price* > pick the *Current price* sensor.

### Setup errors

| Message | Fix |
| --- | --- |
| Enter a full address that starts with the scheme | Add `http://` or `https://` in front of the address. |
| Could not reach the server | Wrong address or port, or the server is not reachable from Home Assistant (firewall, VPN, DNS). |
| The token was rejected | Create a new token in the Rabot app and paste it completely. |
| The server did not find this contract | Check the contract number, and that the server address is for the right environment. |
| This contract is already set up | Each contract can be added once; use *Reconfigure* to change it. |
| Unexpected error | Check Settings > System > Logs for `rabot_energy`. |

### Later changes

- **Other server or token:** Settings > Devices & services > Rabot Energy > three-dot menu of the
  entry > *Reconfigure*. An empty token field keeps the stored token. No need to delete the entry.
- **Expired or revoked token:** Home Assistant shows a *Reauthenticate* notice; enter a new token
  from the Rabot app.
- **Update:** HACS shows new versions; download and restart Home Assistant.
- **Remove:** delete the entry in Settings > Devices & services, then remove the integration in
  HACS and restart.

## Show the prices in a chart

The *Current price* sensor carries the whole preview in its `prices` attribute (a list of
`start`, `end` and `price` in EUR/kWh). The list is kept out of the database, so a chart has to read
the attribute directly. [ApexCharts Card](https://github.com/RomRider/apexcharts-card) does this
with a `data_generator`.

### 1. Install ApexCharts Card

1. HACS > Frontend > search for **ApexCharts Card** > Download.
2. If HACS does not add the resource itself: Settings > Dashboards > three-dot menu > Resources >
   Add resource, URL `/hacsfiles/apexcharts-card/apexcharts-card.js`, type *JavaScript module*.
3. Reload the browser page (hard refresh, or clear the app cache in the companion app).

### 2. Find your entity ID

Settings > Devices & services > Rabot Energy > your device > *Current price* > settings (cog).
The entity ID looks like `sensor.rabot_<contract number>_current_price`. Use exactly that value
below; a wrong ID is the most common reason for an empty chart.

Check that the data is there: Developer tools > States, search for the entity and look for the
`prices` attribute. If it is missing, the first update has not finished yet; wait a minute or
reload the integration.

### 3. Add the card

Dashboard > Edit > Add card > *Manual*, and paste this (replace the entity ID twice):

```yaml
type: custom:apexcharts-card
graph_span: 48h
span:
  start: day
header:
  show: true
  title: Rabot electricity price
  show_states: true
now:
  show: true
  label: now
yaxis:
  - id: price
    decimals: 0
    apex_config:
      title:
        text: ct/kWh
apex_config:
  chart:
    height: 360
  xaxis:
    labels:
      datetimeUTC: false
series:
  - entity: sensor.rabot_12345678_current_price
    name: Now
    yaxis_id: price
    transform: return x * 100;
    unit: ct/kWh
    float_precision: 1
    show:
      in_chart: false
      in_header: true
  - entity: sensor.rabot_12345678_current_price
    name: Price
    yaxis_id: price
    type: area
    curve: stepline
    stroke_width: 2
    opacity: 0.25
    extend_to: false
    unit: ct/kWh
    float_precision: 1
    show:
      in_header: false
    data_generator: |
      return entity.attributes.prices.map((p) => [new Date(p.start).getTime(), p.price * 100]);
```

The first series only shows the current price in the card header; the second draws the curve.
Prices are multiplied by 100 to show cent per kWh; drop `* 100` and the `ct/kWh` texts to chart in
EUR/kWh.

### Optional: colours and a threshold line

Add to the *Price* series to colour the curve by price (values in ct/kWh):

```yaml
    color_threshold:
      - value: 0
        color: '#4caf50'
      - value: 30
        color: '#ffc107'
      - value: 40
        color: '#f44336'
```

And a horizontal line, for example at 40 ct, next to `xaxis` under `apex_config`:

```yaml
  annotations:
    yaxis:
      - y: 40
        borderColor: '#4caf50'
        strokeDashArray: 4
```

### Chart troubleshooting

| Problem | Fix |
| --- | --- |
| "Custom element doesn't exist: apexcharts-card" | The resource is missing (step 1.2) or the page is cached; hard refresh. |
| Card shows an error about `entity.attributes.prices` | Wrong entity ID, or the attribute is not there yet (step 2). Use the *Current price* sensor, not *Next price*. |
| Chart is empty, header shows a price | The price list is empty or the time range does not match; use `graph_span: 48h` with `span.start: day`. |
| Curve is shifted by an hour or two | Keep `datetimeUTC: false` under `xaxis.labels`; the times are converted to your browser time zone. |
| Only future hours, nothing in the past | By design: the chart draws the preview from the API, not the sensor history. |
| Prices look 100 times too small | Missing `* 100`; the sensor reports EUR/kWh. |
| No new data after a while | The service is polled every 30 minutes; check Settings > Devices & services > Rabot Energy for errors or a reauthentication request. |

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
- `priceCap` (null in the samples) and the base provider working price are parsed by the library but
  not exposed as sensors yet.
- The contract number format is not validated by the config flow.
- Prices are assumed to be in EUR (the schema only says cent).
- The library is bundled under `_lib` because `rabot-energy` is not on PyPI yet. Before a Home
  Assistant Core submission it must be published and this copy removed.
- No config-flow tests yet (they need `pytest-homeassistant-custom-component`, which needs the
  Python version of the current Home Assistant release), no diagnostics, no `get_prices` action,
  no logo image (only the icon is in `custom_components/rabot_energy/brand/`).
- `codeowners` in `manifest.json` is empty.

## Development

```shell
pip install -r requirements_test.txt
pytest          # price logic tests, no Home Assistant needed
```

## Licence

Apache-2.0
