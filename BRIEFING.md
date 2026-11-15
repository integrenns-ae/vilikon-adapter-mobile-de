Wofür: das eigene Händlerkonto des Betriebs bei mobile.de – Inserate, Preise, Bewertungen und Kundenanfragen.

- Lesen geht sofort: `list_ads` (Kurzform, `search` filtert), `get_ad`, `price_rating`, `ad_statistics`, `list_leads`, `list_ratings`.
- Jede Änderung (`change_price`, `set_reserved`, `renew_ad`, `delete_ad`, `create_ad`, `set_images`, `send_direct_offer`, `reply_rating`, `invite_rating`, `set_lead_status`) wird eine Karte für den Inhaber. Schreib in die Zusammenfassung, was sich ändert, mit Fahrzeug und altem und neuem Wert. Erst sein Ja ändert etwas bei mobile.de.
- Preise sind Endkundenpreise brutto. Nenne Preise und Kilometer so, wie mobile.de sie liefert, nie geschätzt.
- Neue Kundenanfragen landen von selbst im Lead-Eingang (Kanal „mobile.de“). Antworten von Interessenten und verpasste Anrufe zu bekannten Anfragen kommen als Vorgang. Ist eine Anfrage erledigt, melde mobile.de den Stand mit `set_lead_status` (die Nummer steht als `lead_id` dabei).
- Statistik nur ansehen, nie in Listen oder Notizen ablegen: mobile.de erlaubt die Zahlen nur für die Laufzeit des Inserats.
- Direktangebote ohne Telefonnummer und E-Mail-Adresse, 3 bis 1000 Zeichen, 1 bis 14 Tage.
- Bilder für `create_ad` und `set_images`: am besten übergebene Fotos (`{"image": "img-…"}`, siehe unten), sonst eine Adresse (`https://…`) oder `base64` eines JPG bis 2 MB. Wie viele erlaubt sind, sagt `seller_info`.
- Feste Werte (Marke, Modell, Kategorie, Kraftstoff, Getriebe, Türen, Schadstoffklasse …) holst du mit `reference_data`; ins Inserat kommt der `name`, nie die Beschreibung. Rate nie einen Code.
- Meldet eine Funktion, dass etwas nicht freigeschaltet ist (Statistik auf Anfrage, Bewertungen ab Gold-Paket), sag das dem Inhaber so; das klärt er mit mobile.de.

## Ein Fahrzeug inserieren

1. **Fahrzeugschein lesen**, wenn er im Gespräch liegt (Zulassungsbescheinigung Teil I): B Erstzulassung → `firstRegistration` (JJJJMM), D.1 Marke → `make`, D.2/D.3 Typ und Handelsbezeichnung → `model` und `modelDescription` (höchstens 48 Zeichen, wird der Titel), E → `vin` (Großbuchstaben), P.1 Hubraum → `cubicCapacity`, P.2 Leistung in kW → `power`, P.3 Kraftstoff → `fuel`, 2.1/2.2 → `kba.hsn`/`kba.tsn`, S.1 → `seats`. Die Codes für Marke, Modell und Kraftstoff suchst du mit `reference_data` heraus. Halter und Anschrift (Feld C) gehören nie ins Inserat, in Notizen oder Listen.
2. **Fragen, was fehlt**, in einer Nachricht, kurz: Kilometerstand, Preis, Unfall- und Schadensfreiheit, Farbe und Ausstattung, die zählt, 2–3 Fotos (falls noch keine da sind) und: „Was ist das stärkste Verkaufsargument?“ Rate nichts davon.
3. **Fotos übergeben**: Jedes Foto aus dem Gespräch (z. B. `chat/<datum>/golf-1.jpg`) einzeln mit `werkzeug_aufrufen` an dieses Werkzeug: `methode` POST, `pfad` `ki/images`, `datei` der Pfad in deiner Arbeitsmappe. Die Antwort nennt eine Nummer `img-…`. Das Foto bleibt dabei hier, nichts geht zu mobile.de. HEIC und große Fotos werden selbst passend gemacht. Fehlt dir `werkzeug_aufrufen` für dieses Werkzeug, bitte den Inhaber, dich auf der Seite „Werkzeuge“ dafür einzutragen.
4. **Text schreiben** für `description` (höchstens 5000 Zeichen): das stärkste Argument zuerst, dann Zustand, Ausstattung, Wartung, nur Fakten, die du hast. Keine Telefonnummern oder Mail-Adressen, die nicht ausdrücklich gewünscht sind.
5. **Zur Freigabe vorlegen** mit `create_ad`: `ad` mit mindestens `vehicleClass`, `category`, `make`, `model`, `price.consumerPriceGross`, dazu alles Bekannte; `images` mit den `img-…`-Nummern in der gewünschten Reihenfolge, das beste Foto zuerst. In die Zusammenfassung: Fahrzeug, Preis, Zahl der Bilder, der erste Satz des Textes.
6. **Nach dem Ja** prüfst du mit `get_ad`, ob Daten und Bilder angekommen sind, und nennst dem Inhaber die Inseratsnummer.
