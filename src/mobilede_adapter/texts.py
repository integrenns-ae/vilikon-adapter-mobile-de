"""Every sentence a person reads, in German and US English. German is the source."""

from __future__ import annotations

DE: dict[str, str] = {
    # set-up
    "not_configured": "Die Zugangsdaten für mobile.de fehlen (MOBILE_DE_USER und MOBILE_DE_PASSWORD).",
    "no_seller": "Zu diesem API-Zugang gehört kein Händlerkonto bei mobile.de.",
    "several_sellers": "Zu diesem API-Zugang gehören mehrere Händlerkonten ({ids}). Bitte MOBILE_DE_SELLER_ID setzen.",
    "check_ok": "Verbindung zu mobile.de steht: {name} (Händlernummer {id}).",
    "check_leads_off": "Inserate gehen, die Lead API ist für diesen Zugang aber nicht freigeschaltet.",
    # errors from mobile.de
    "http_401": "mobile.de lehnt die Anmeldung ab. Benutzername oder Passwort des API-Zugangs stimmen nicht.",
    "http_403": "Der API-Zugang darf das nicht. Manche Funktionen schaltet mobile.de erst auf Anfrage frei "
    "(Statistik) oder ab einem bestimmten Paket (Bewertungen ab Gold).",
    "http_404": "Das gibt es bei mobile.de nicht oder es gehört nicht zu diesem Händlerkonto.",
    "http_409": "mobile.de meldet einen Konflikt. Vermutlich hat sich das Inserat gerade geändert; bitte noch einmal.",
    "http_5xx": "mobile.de ist gerade nicht erreichbar. Bitte später noch einmal versuchen.",
    "http_other": "mobile.de antwortet mit Fehler {status}.",
    "unreachable": "mobile.de ist nicht erreichbar: {error}",
    "invalid_value": "mobile.de lehnt den Wert für „{path}“ ab.",
    "missing_value": "mobile.de vermisst eine Angabe für „{path}“.",
    "not_a_jpeg": "Ein Bild ist kein JPG. mobile.de nimmt nur JPG.",
    "too_many_images": "Zu viele Bilder für dieses Inserat.",
    "concurrent_update": "Die Bilder dieses Inserats werden gerade schon geändert. Bitte gleich noch einmal.",
    "error_key": "mobile.de meldet: {key}",
    "id_invalid": "„{id}“ ist keine gültige Nummer.",
    # checks before a write
    "price_invalid": "Der Preis muss eine Zahl über 0 sein.",
    "ad_has_no_price": "Das Inserat hat keinen Preis, den ich ändern könnte.",
    "comment_length": "Die Antwort braucht 1 bis 1000 Zeichen.",
    "offer_length": "Das Angebot braucht 3 bis 1000 Zeichen.",
    "offer_latin1": "Das Angebot enthält Zeichen, die mobile.de nicht annimmt (nur westeuropäische Schrift).",
    "offer_contact": "Im Angebot dürfen keine Telefonnummern oder E-Mail-Adressen stehen.",
    "offer_days": "Das Angebot gilt 1 bis 14 Tage.",
    "email_invalid": "Das ist keine gültige E-Mail-Adresse.",
    "status_invalid": "Status muss einer von {values} sein.",
    "images_missing": "Es fehlen Bilder.",
    "image_source": "Ein Bild braucht „image“ (ein übergebenes Foto), „url“ (https) oder „base64“.",
    "image_too_big": "Ein Bild ist größer als 2 MB.",
    "image_fetch": "Ein Bild ließ sich nicht laden: {error}",
    "image_max": "mobile.de erlaubt für dieses Händlerkonto höchstens {max} Bilder, es sind {count}.",
    "image_unreadable": "Die Datei ist kein Bild, das ich lesen kann (JPG, PNG, HEIC, WebP).",
    "image_input_too_big": "Die Datei ist größer als 30 MB.",
    "image_unknown": "Dieses Bild kenne ich nicht (mehr). Bitte das Foto noch einmal übergeben; "
    "gemerkt wird es eine Woche.",
    "image_missing_file": "Es kam keine Datei an. Das Foto als Datei schicken (Feld beliebig) oder als Bild im Rumpf.",
    "image_staged": "Foto bereit als {image} ({width} × {height} Pixel). "
    'Für create_ad oder set_images: {{"image": "{image}"}}.',
    "refdata_invalid": "Unbekannte Art oder ungültiger Name. Arten: makes, models, categories "
    "oder eine Tabelle wie fuels, gearboxes, colors.",
    "refdata_make_missing": "Für models fehlt make, z. B. make=VW.",
    "ad_invalid": "Das Inserat braucht mindestens Fahrzeugklasse, Marke und Preis.",
    # write guard
    "writes_off": "Änderungen bei mobile.de sind ausgeschaltet (MOBILE_DE_WRITES=off).",
    "confirm_needed": "Noch nichts geändert. Zum Ausführen dieselbe Funktion mit denselben Angaben und "
    "confirmation=„{code}“ aufrufen (gültig {minutes} Minuten).",
    "confirm_wrong": "Der Bestätigungscode passt nicht oder ist abgelaufen. Noch nichts geändert; bitte neu anfordern.",
    "approval_needed": "Änderungen über diesen Weg gehen nur nach Freigabe im Cockpit.",
    "already_done": "Schon erledigt.",
    # previews and results
    "preview_price": "Preis von {ad}: {old} → {new}",
    "done_price": "Preis von {ad} ist jetzt {new}.",
    "preview_reserved_on": "{ad} als reserviert markieren",
    "preview_reserved_off": "Reservierung von {ad} aufheben",
    "done_reserved_on": "{ad} ist als reserviert markiert.",
    "done_reserved_off": "{ad} ist nicht mehr reserviert.",
    "preview_renew": "{ad} erneuern (erscheint wieder als neu)",
    "done_renew": "{ad} ist erneuert.",
    "preview_delete": "{ad} bei mobile.de löschen, mit allen Bildern. Lässt sich nicht rückgängig machen.",
    "done_delete": "{ad} ist gelöscht.",
    "preview_reply": "Antwort auf Bewertung {id}: „{text}“",
    "done_reply": "Antwort auf Bewertung {id} ist veröffentlicht.",
    "preview_invite": "Käufer {email} zur Bewertung für {ad} einladen",
    "done_invite": "Einladung zur Bewertung an {email} ist verschickt.",
    "preview_offer": "Direktangebot zu {ad}, {days} Tage gültig: „{text}“",
    "done_offer": "Direktangebot zu {ad} ist verschickt.",
    "preview_status": "Anfrage {id} auf „{status}“ setzen",
    "done_status": "Anfrage {id} steht bei mobile.de auf „{status}“.",
    "preview_images": "Bilder von {ad} ersetzen: {count} neue Bilder",
    "done_images": "{ad} hat jetzt {count} Bilder.",
    "preview_create": "Neues Inserat: {ad}, {price}, {count} Bilder",
    "done_create": "Inserat {ad} ist angelegt (Nummer {id}).",
    "done_create_existing": "Dieses Inserat gab es schon (Nummer {id}); nichts doppelt angelegt.",
    # leads
    "lead_subject": "Anfrage zu {vehicle}",
    "lead_subject_leasing": "Leasing-Anfrage zu {vehicle}",
    "lead_subject_call": "Anruf zu {vehicle}",
    "lead_subject_missed_call": "Verpasster Anruf zu {vehicle}",
    "lead_vehicle_unknown": "einem Fahrzeug",
    "lead_ad": "Inserat {id}",
    "lead_internal": "interne Nummer {id}",
    "lead_from_kleinanzeigen": "über Kleinanzeigen",
    "lead_wishes": "Wünsche: {list}",
    "wish_test_drive": "Probefahrt",
    "wish_trade_in": "Inzahlungnahme",
    "wish_delivery": "Lieferung",
    "wish_financing": "Finanzierung",
    "wish_leasing": "Leasing",
    "lead_leasing": "Leasing: {months} Monate, {mileage} km/Jahr, Rate {rate}",
    "lead_call": "Anruf {answered}, {seconds} s, von {number}",
    "lead_call_answered": "angenommen",
    "lead_call_missed": "nicht angenommen",
    "lead_call_summary": "Zusammenfassung: {text}",
    "event_reply_title": "Antwort von {name}",
    "event_resubmit_title": "Erneute Anfrage von {name}",
    "event_missed_call_title": "Verpasster Anruf von {name}",
    "event_buyer": "einem Interessenten",
    # dashboard card
    "card_text": "neue Anfragen in 7 Tagen",
    # status page
    "page_title": "mobile.de",
    "page_ok": "Der Adapter läuft.",
}

EN: dict[str, str] = {
    "not_configured": "The mobile.de credentials are missing (MOBILE_DE_USER and MOBILE_DE_PASSWORD).",
    "no_seller": "No mobile.de dealer account belongs to this API user.",
    "several_sellers": "Several dealer accounts belong to this API user ({ids}). Please set MOBILE_DE_SELLER_ID.",
    "check_ok": "Connected to mobile.de: {name} (dealer number {id}).",
    "check_leads_off": "Listings work, but the Lead API is not enabled for this API user.",
    "http_401": "mobile.de rejects the sign-in. The API user name or password is wrong.",
    "http_403": "The API user may not do this. mobile.de enables some features only on request (statistics) or "
    "from a certain package (ratings from Gold).",
    "http_404": "This does not exist at mobile.de or does not belong to this dealer account.",
    "http_409": "mobile.de reports a conflict. The listing probably just changed; please try again.",
    "http_5xx": "mobile.de is not reachable right now. Please try again later.",
    "http_other": "mobile.de answers with error {status}.",
    "unreachable": "mobile.de is not reachable: {error}",
    "invalid_value": "mobile.de rejects the value for “{path}”.",
    "missing_value": "mobile.de is missing a value for “{path}”.",
    "not_a_jpeg": "An image is not a JPG. mobile.de only takes JPG.",
    "too_many_images": "Too many images for this listing.",
    "concurrent_update": "The images of this listing are already being changed. Please try again in a moment.",
    "error_key": "mobile.de reports: {key}",
    "id_invalid": "“{id}” is not a valid number.",
    "price_invalid": "The price must be a number above 0.",
    "ad_has_no_price": "The listing has no price I could change.",
    "comment_length": "The reply needs 1 to 1000 characters.",
    "offer_length": "The offer needs 3 to 1000 characters.",
    "offer_latin1": "The offer contains characters mobile.de does not accept (Western European script only).",
    "offer_contact": "The offer must not contain phone numbers or e-mail addresses.",
    "offer_days": "The offer is valid for 1 to 14 days.",
    "email_invalid": "That is not a valid e-mail address.",
    "status_invalid": "Status must be one of {values}.",
    "images_missing": "Images are missing.",
    "image_source": "An image needs “image” (a handed-over photo), “url” (https) or “base64”.",
    "image_too_big": "An image is larger than 2 MB.",
    "image_fetch": "An image could not be loaded: {error}",
    "image_max": "mobile.de allows at most {max} images for this dealer account, there are {count}.",
    "image_unreadable": "The file is not an image I can read (JPG, PNG, HEIC, WebP).",
    "image_input_too_big": "The file is larger than 30 MB.",
    "image_unknown": "I do not know this image (any more). Please hand over the photo again; it is kept for a week.",
    "image_missing_file": "No file arrived. Send the photo as a file (any field) or as an image body.",
    "image_staged": "Photo ready as {image} ({width} × {height} pixels). "
    'For create_ad or set_images: {{"image": "{image}"}}.',
    "refdata_invalid": "Unknown kind or invalid name. Kinds: makes, models, categories "
    "or a table such as fuels, gearboxes, colors.",
    "refdata_make_missing": "models needs make, e.g. make=VW.",
    "ad_invalid": "The listing needs at least vehicle class, make and price.",
    "writes_off": "Changes at mobile.de are switched off (MOBILE_DE_WRITES=off).",
    "confirm_needed": "Nothing changed yet. To carry it out, call the same function with the same values and "
    "confirmation=“{code}” (valid for {minutes} minutes).",
    "confirm_wrong": "The confirmation code does not match or has expired. Nothing changed; please request a new one.",
    "approval_needed": "Changes through this route need an approval in the cockpit.",
    "already_done": "Already done.",
    "preview_price": "Price of {ad}: {old} → {new}",
    "done_price": "The price of {ad} is now {new}.",
    "preview_reserved_on": "Mark {ad} as reserved",
    "preview_reserved_off": "Remove the reservation of {ad}",
    "done_reserved_on": "{ad} is marked as reserved.",
    "done_reserved_off": "{ad} is no longer reserved.",
    "preview_renew": "Renew {ad} (shows as new again)",
    "done_renew": "{ad} is renewed.",
    "preview_delete": "Delete {ad} at mobile.de, with all images. This cannot be undone.",
    "done_delete": "{ad} is deleted.",
    "preview_reply": "Reply to rating {id}: “{text}”",
    "done_reply": "The reply to rating {id} is published.",
    "preview_invite": "Invite buyer {email} to rate {ad}",
    "done_invite": "The rating invitation to {email} is sent.",
    "preview_offer": "Direct offer for {ad}, valid {days} days: “{text}”",
    "done_offer": "The direct offer for {ad} is sent.",
    "preview_status": "Set inquiry {id} to “{status}”",
    "done_status": "Inquiry {id} is “{status}” at mobile.de.",
    "preview_images": "Replace the images of {ad}: {count} new images",
    "done_images": "{ad} now has {count} images.",
    "preview_create": "New listing: {ad}, {price}, {count} images",
    "done_create": "Listing {ad} is created (number {id}).",
    "done_create_existing": "This listing already existed (number {id}); nothing created twice.",
    "lead_subject": "Inquiry about {vehicle}",
    "lead_subject_leasing": "Leasing inquiry about {vehicle}",
    "lead_subject_call": "Call about {vehicle}",
    "lead_subject_missed_call": "Missed call about {vehicle}",
    "lead_vehicle_unknown": "a vehicle",
    "lead_ad": "listing {id}",
    "lead_internal": "internal number {id}",
    "lead_from_kleinanzeigen": "via Kleinanzeigen",
    "lead_wishes": "Wishes: {list}",
    "wish_test_drive": "test drive",
    "wish_trade_in": "trade-in",
    "wish_delivery": "delivery",
    "wish_financing": "financing",
    "wish_leasing": "leasing",
    "lead_leasing": "Leasing: {months} months, {mileage} km/year, rate {rate}",
    "lead_call": "Call {answered}, {seconds} s, from {number}",
    "lead_call_answered": "answered",
    "lead_call_missed": "not answered",
    "lead_call_summary": "Summary: {text}",
    "event_reply_title": "Reply from {name}",
    "event_resubmit_title": "New inquiry from {name}",
    "event_missed_call_title": "Missed call from {name}",
    "event_buyer": "a prospect",
    "card_text": "new inquiries in 7 days",
    "page_title": "mobile.de",
    "page_ok": "The adapter is running.",
}

CATALOGS = {"de": DE, "en": EN}


class Texts:
    def __init__(self, lang: str = "de") -> None:
        self.lang = lang if lang in CATALOGS else "de"
        self._catalog = CATALOGS[self.lang]

    def __call__(self, key: str, **values: object) -> str:
        return self._catalog[key].format(**values)

    def money(self, amount: float | int | None, currency: str = "EUR") -> str:
        if amount is None:
            return "–"
        whole = round(float(amount), 2)
        digits = f"{whole:,.2f}" if whole % 1 else f"{whole:,.0f}"
        if self.lang == "de":
            digits = digits.replace(",", "§").replace(".", ",").replace("§", ".")
            return f"{digits} €" if currency == "EUR" else f"{digits} {currency}"
        return f"€{digits}" if currency == "EUR" else f"{digits} {currency}"
