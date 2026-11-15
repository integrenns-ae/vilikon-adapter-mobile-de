What for: the business's own dealer account at mobile.de – listings, prices, ratings and customer inquiries.

- Reading works right away: `list_ads` (short form, `search` filters), `get_ad`, `price_rating`, `ad_statistics`, `list_leads`, `list_ratings`.
- Every change (`change_price`, `set_reserved`, `renew_ad`, `delete_ad`, `create_ad`, `set_images`, `send_direct_offer`, `reply_rating`, `invite_rating`, `set_lead_status`) becomes a card for the owner. Write in the summary what changes, with the vehicle and the old and new value. Only their yes changes anything at mobile.de.
- Prices are gross consumer prices. State prices and mileage as mobile.de delivers them, never estimated.
- New customer inquiries arrive in the lead intake by themselves (channel “mobile.de”). Replies from prospects and missed calls on known inquiries arrive as cases. When an inquiry is settled, report its state to mobile.de with `set_lead_status` (the number is given as `lead_id`).
- Look at statistics, never keep them in lists or notes: mobile.de allows the numbers only for the listing's lifetime.
- Direct offers without phone numbers or e-mail addresses, 3 to 1000 characters, 1 to 14 days.
- Images for `create_ad` and `set_images`: JPG up to 2 MB, as an address (`https://…`) or `base64`. `seller_info` says how many are allowed.
- If a function reports that something is not enabled (statistics on request, ratings from the Gold package), tell the owner so; they settle it with mobile.de.
