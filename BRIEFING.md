Wofür: das eigene Händlerkonto des Betriebs bei mobile.de – Inserate, Preise, Bewertungen und Kundenanfragen.

- Lesen geht sofort: `list_ads` (Kurzform, `search` filtert), `get_ad`, `price_rating`, `ad_statistics`, `list_leads`, `list_ratings`.
- Jede Änderung (`change_price`, `set_reserved`, `renew_ad`, `delete_ad`, `create_ad`, `set_images`, `send_direct_offer`, `reply_rating`, `invite_rating`, `set_lead_status`) wird eine Karte für den Inhaber. Schreib in die Zusammenfassung, was sich ändert, mit Fahrzeug und altem und neuem Wert. Erst sein Ja ändert etwas bei mobile.de.
- Preise sind Endkundenpreise brutto. Nenne Preise und Kilometer so, wie mobile.de sie liefert, nie geschätzt.
- Neue Kundenanfragen landen von selbst im Lead-Eingang (Kanal „mobile.de“). Antworten von Interessenten und verpasste Anrufe zu bekannten Anfragen kommen als Vorgang. Ist eine Anfrage erledigt, melde mobile.de den Stand mit `set_lead_status` (die Nummer steht als `lead_id` dabei).
- Statistik nur ansehen, nie in Listen oder Notizen ablegen: mobile.de erlaubt die Zahlen nur für die Laufzeit des Inserats.
- Direktangebote ohne Telefonnummer und E-Mail-Adresse, 3 bis 1000 Zeichen, 1 bis 14 Tage.
- Bilder für `create_ad` und `set_images`: JPG bis 2 MB, als Adresse (`https://…`) oder `base64`. Wie viele erlaubt sind, sagt `seller_info`.
- Meldet eine Funktion, dass etwas nicht freigeschaltet ist (Statistik auf Anfrage, Bewertungen ab Gold-Paket), sag das dem Inhaber so; das klärt er mit mobile.de.
