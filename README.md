# vilikon-adapter-mobile-de

An adapter for **one car dealer's own mobile.de account**: listings, prices, statistics, ratings and customer
inquiries. MCP in front, the official mobile.de REST APIs behind.

- **On its own**: an MCP server (stdio or Streamable HTTP) for any MCP client.
- **In Vilikon**: a tool with `MODULE.json` (functions for employees, every change behind the owner's approval) and a
  lead channel (`vilikon.kanal/1`) that hands new inquiries to the cockpit's lead intake.

This repository is a template. Each dealer runs their own copy with their own mobile.de API user, for their own
account only. The adapter never serves several dealers and never holds anyone else's credentials.

```
MCP client                         Vilikon cockpit
    │ /mcp or stdio                    │ /ki/…  (MODULE.json, vilikon.kanal/1)
    └──────────────┬───────────────────┘
            service.py   checks, read-change-write, previews
            client.py    Seller API + Lead API, HTTP basic auth, retries
                   │
            services.mobile.de
```

## What it can do

| Read | Change (preview first) |
|---|---|
| `seller_info`, `list_ads`, `get_ad` | `change_price`, `set_reserved`, `renew_ad`, `delete_ad` |
| `ad_statistics`, `price_rating`, `preview_price_rating` | `create_ad` (with images), `set_images`, `send_direct_offer` |
| `list_ratings`, `rating_overview` | `reply_rating`, `invite_rating` |
| `list_leads`, `check_connection`, `reference_data` | `set_lead_status` |
| `stage_image` (kept locally, nothing goes to mobile.de) | |

- **Listings**: mobile.de wants the complete listing on every update, so a change fetches the listing, changes one
  field and sends it back whole. Changing the gross price recomputes the net price from the listing's VAT rate.
- **Images**: mobile.de takes JPG only, up to 2 MB each, at most the dealer's `maxImages`, uploaded one after the
  other. Hand a photo over with `stage_image` (a file path or base64; JPG, PNG, HEIC, WebP): it is turned upright,
  stripped of its metadata (a phone writes the location into it), fitted below 2 MB and kept in `DATA_DIR/images` for
  a week under an id. Pass each image as `{"image": "img-…"}`, `{"url": "https://…"}` or `{"base64": "…"}`.
- **Reference data**: make, model, category, fuel, gearbox and the other fixed values are codes from mobile.de's
  reference tables (`/refdata`, no login needed). `reference_data` looks them up for the dealer's site, with a search,
  and keeps them for a day.
- **New listings** carry an `X-Mobile-Insertion-Request-Id` derived from their content: a repeat after a timeout
  creates nothing twice.
- **Inquiries**: mobile.de has no push. The adapter polls the Lead API events with its cursor, merges the events of
  one lead (first inquiry, the buyer's reply, calls) and keeps them for 30 days in `DATA_DIR/leads.json` (mode 0600).
- **Statistics** are passed through and never stored: mobile.de allows them only for the listing's lifetime.

## Getting access at mobile.de

The API user is not the login for the dealer area. The dealer asks mobile.de customer service to enable an API user
for their own account: e-mail to service@team.mobile.de with customer number, company name, a request to activate
the Seller API and the Lead API, and a technical and a contractual contact. A sandbox account can be requested the
same way. Statistics need an extra permission, ratings at least the Gold package; without them those functions say
so in one sentence.

Docs: [Seller API](https://services.mobile.de/docs/seller-api.html),
[Lead API](https://services.mobile.de/docs/lead-api.html).

## Settings

All from the environment, never from a file.

| Variable | Meaning |
|---|---|
| `MOBILE_DE_USER`, `MOBILE_DE_PASSWORD` | The dealer's API user |
| `MOBILE_DE_SELLER_ID` | Only if several dealer accounts belong to the API user |
| `MOBILE_DE_SANDBOX` | `on` for `services.sandbox.mobile.de` |
| `MOBILE_DE_WRITES` | `confirm` (default): a change returns a preview and a code first; `on`: no second step; `off`: read only |
| `MOBILE_DE_LANG` | `de` (default) or `en` for every sentence the adapter returns |
| `DATA_DIR` | Where the lead cursor and the inquiries are kept |
| `ADAPTER_TOKEN` | Bearer token for `/mcp` over HTTP; required unless the server listens on loopback only |
| `HOST`, `PORT` | Default `127.0.0.1:8080` |

## Running it on its own

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt .
```

For a local MCP client (stdio), for example in a client's server list:

```json
{"command": "/path/to/.venv/bin/mobilede-adapter", "args": ["stdio"],
 "env": {"MOBILE_DE_USER": "…", "MOBILE_DE_PASSWORD": "…", "DATA_DIR": "/path/to/data"}}
```

Over HTTP (MCP at `/mcp`):

```bash
ADAPTER_TOKEN=… .venv/bin/mobilede-adapter serve
```

With `MOBILE_DE_WRITES=confirm` a change works in two calls: the first returns `preview` and `confirmation`, the
second with the same values and that `confirmation` carries it out. A code is valid for 10 minutes and works once.

## Running it in Vilikon

On an instance with the adapter catalog the IT Specialist does all of this with one tool call (`adapter_install`),
driven by `ADAPTER.json`, and the owner types the credentials into a card in the chat. By hand, it goes like this:

1. A tool project with its own repository in the instance's GitHub account, filled with a copy of this repository.
2. Build `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt .`, start
   `.venv/bin/python -m mobilede_adapter serve` (the cockpit moves the folder on publishing, so the start must not
   rely on the paths baked into `.venv/bin` scripts).
3. On an English instance, copy `vilikon/en/MODULE.json` and `vilikon/en/BRIEFING.md` over the German ones in the
   root.
4. Request the credentials `MOBILE_DE_USER`, `MOBILE_DE_PASSWORD` (and `MOBILE_DE_SELLER_ID` if needed) with
   `werkzeug_zugang_anfordern`; the owner enters them.
5. Let the employees who list vehicles use the tool (the “Tools” page): module functions send JSON only, so a photo
   reaches `ki/images` through the generic tool call, which sends a file of the employee's workspace.
6. Propose the change. Once the owner approves it, the tool runs, the rights `modul.mobilede.*` can be granted, the
   channel “mobile.de” appears under acquisition and `ki/pruefen` tells whether the credentials work.

Inside Vilikon (`BASE_PATH` below `/werkzeug/`) the `/ki/` paths are on and `/mcp` is off unless `ADAPTER_TOKEN` is
set. A change through `/ki/` happens only with the cockpit's `X-Vilikon-Freigabe` header, which it sends after the
owner's yes; the same approval twice does the work once.

| Path | For |
|---|---|
| `GET ki/kanal/leads?seit=` | New inquiries as `vilikon.lead/1`, `externe_id` `mobilede-<leadId>` |
| `GET ki/ereignisse?seit=` | The buyer answered, asked again, or a call was missed, on a known inquiry |
| `GET ki/karte` | Dashboard card: inquiries of the last 7 days |
| `GET ki/pruefen` | Whether the credentials work for both APIs |
| `POST ki/images` | A photo as a file (multipart, any field) or as the body; answers its id. No approval: it stays here |

`ADAPTER.json` describes build, start, check and credentials for Vilikon's future adapter catalog.

## Development

```bash
.venv/bin/pip install -e ".[dev]" && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The tests run against a stand-in for mobile.de shaped after the examples in its documentation; all data in them is
invented. Not covered without a real API user: mobile.de's actual limits and error answers.

## Licence

MIT, see `LICENSE`.
