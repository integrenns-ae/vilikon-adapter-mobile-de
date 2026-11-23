What for: the business's own dealer account at mobile.de – listings, prices, ratings and customer inquiries.

- Reading works right away: `list_ads` (short form, `search` filters), `get_ad`, `price_rating`, `ad_statistics`, `list_leads`, `list_ratings`.
- Every change (`change_price`, `set_reserved`, `renew_ad`, `delete_ad`, `create_ad`, `set_images`, `send_direct_offer`, `reply_rating`, `invite_rating`, `set_lead_status`) becomes a card for the owner. Write in the summary what changes, with the vehicle and the old and new value. Only their yes changes anything at mobile.de.
- Prices are gross consumer prices. State prices and mileage as mobile.de delivers them, never estimated.
- New customer inquiries arrive in the lead intake by themselves (channel “mobile.de”). Replies from prospects and missed calls on known inquiries arrive as cases. When an inquiry is settled, report its state to mobile.de with `set_lead_status` (the number is given as `lead_id`).
- If the Lead API is not enabled (`list_leads` then says so), inquiries come by e-mail only; nothing from mobile.de appears in the lead intake. A prospect's name, phone and e-mail come only from the Lead API, never from the listings.
- Look at statistics, never keep them in lists or notes: mobile.de allows the numbers only for the listing's lifetime.
- Direct offers without phone numbers or e-mail addresses, 3 to 1000 characters, 1 to 14 days.
- Images for `create_ad` and `set_images`: preferably handed-over photos (`{"image": "img-…"}`, see below), else an address (`https://…`) or `base64` of a JPG up to 2 MB. `seller_info` says how many are allowed.
- Fixed values (make, model, category, fuel, gearbox, doors, emission class …) come from `reference_data`; the listing takes the `name`, never the description. Never guess a code.
- If a function reports that something is not enabled (statistics on request, ratings from the Gold package), tell the owner so; they settle it with mobile.de.

## Listing a vehicle

1. **Read the registration document** if it is in the conversation (German Zulassungsbescheinigung Teil I): B first registration → `firstRegistration` (YYYYMM), D.1 make → `make`, D.2/D.3 type and trade name → `model` and `modelDescription` (at most 48 characters, becomes the title), E → `vin` (capital letters), P.1 displacement → `cubicCapacity`, P.2 power in kW → `power`, P.3 fuel → `fuel`, 2.1/2.2 → `kba.hsn`/`kba.tsn`, S.1 → `seats`. Look up the codes for make, model and fuel with `reference_data`. The holder and their address (field C) never go into the listing, notes or lists.
2. **Ask for what is missing**, in one short message: mileage, price, whether it is accident- and damage-free, colour and the equipment that matters, 2–3 photos (if there are none yet) and: “What is the strongest selling point?” Guess none of it.
3. **Hand over the photos**: each photo from the conversation (e.g. `chat/<date>/golf-1.jpg`) on its own with `werkzeug_aufrufen` to this tool: `methode` POST, `pfad` `ki/images`, `datei` the path in your workspace. The answer gives a number `img-…`. The photo stays here, nothing goes to mobile.de. HEIC and large photos are fitted by themselves. If you lack `werkzeug_aufrufen` for this tool, ask the owner to add you on the “Tools” page.
4. **Write the text** for `description` (at most 5000 characters): the strongest point first, then condition, equipment, service history, only facts you have. No phone numbers or e-mail addresses unless explicitly wanted.
5. **Propose it for approval** with `create_ad`: `ad` with at least `vehicleClass`, `category`, `make`, `model`, `price.consumerPriceGross`, plus everything known; `images` with the `img-…` numbers in the wanted order, the best photo first. In the summary: vehicle, price, number of images, the first sentence of the text.
6. **After the yes**, check with `get_ad` that data and images arrived, and tell the owner the listing number.
