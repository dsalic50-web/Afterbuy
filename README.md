# Afterbuy – bot za oglase za preprodaju

Bot svaki dan pretražuje oglasnike (OLX.ba, Njuškalo), procjenjuje za koliko se
artikl realno može preprodati i javlja ti **samo oglase na kojima možeš zaraditi
60 % ili više** – na Telegram i u web nadzornoj ploči.

## Kako bot procjenjuje zaradu

Za svaku tvoju pretragu (npr. *iPhone 13 128GB*):

1. skupi sve oglase s portala i spremi njihove cijene u bazu (povijest zadnjih 30 dana),
2. izbaci nebitne oglase (`kupujem`, `zamjena`, `neispravan`, `za dijelove`, maske…)
   i ekstremne cijene,
3. **tržišna cijena** = medijan cijena usporedivih oglasa,
4. **očekivana prodaja** = tržišna cijena × 0,90 (realno prodaš malo ispod tražene),
5. **zarada** = prodaja − provizija − fiksni trošak (gorivo/dostava) − kupovna cijena,
6. **marža** = zarada / kupovna cijena → ako je **≥ 60 %**, oglas je prilika.

Oglasi s cijenom ispod 25 % tržišne označeni su kao **sumnjivi** (česte prevare).
Svaki oglas javlja se samo jednom.

## Pokretanje

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml      # uredi svoje pretrage
python -m afterbuy --demo run           # probaj s lažnim oglasima (bez interneta)
python -m afterbuy run                  # jedna prava pretraga odmah
python -m afterbuy serve                # web ploča na http://127.0.0.1:5000 + pretraga svaki dan u run_at
```

Ostale naredbe:

| Naredba | Što radi |
|---|---|
| `python -m afterbuy schedule` | samo bot, pretraga svaki dan u `run_at` (bez web ploče) |
| `python -m afterbuy serve --no-schedule` | samo web ploča |
| `python -m afterbuy serve --host 0.0.0.0` | ploča dostupna i s mobitela u istoj mreži |

Umjesto `schedule` možeš koristiti i cron: `0 8 * * * cd /put/do/Afterbuy && python -m afterbuy run`.

## Telegram obavijesti

1. U Telegramu otvori **@BotFather** → `/newbot` → dobit ćeš *token*.
2. Pošalji bilo koju poruku svom novom botu, pa otvori **@userinfobot** da saznaš svoj *chat_id*.
3. Upiši ih u `config.yaml` pod `notify.telegram` (ili kao varijable okoline
   `AFTERBUY_TELEGRAM_TOKEN` i `AFTERBUY_TELEGRAM_CHAT_ID`).

## Web ploča

- prilike sortirane po marži ili zaradi, filtrirane po statusu i pretrazi,
- svaku priliku označiš kao *kupljeno* / *prodano* / *ignorirano* i upišeš stvarne cijene,
- ploča zbraja tvoju **stvarno ostvarenu zaradu**,
- gumb *Pokreni pretragu sad*.

## Savjeti za dobre pretrage

- Budi konkretan: `iphone 13 128gb` s `exclude: [pro, mini]` daje puno točniju
  tržišnu cijenu nego samo `iphone`.
- `must_include: ["ps5|playstation 5"]` – naslov mora sadržavati *ps5* **ili** *playstation 5*.
- Ako za neki artikl ima malo oglasa, upiši `market_price` (cijenu za koju znaš da prodaješ).
- Prvih par dana baza tek skuplja povijest cijena, pa procjene s vremenom postaju bolje.

## Napomene

- Parseri za OLX.ba i Njuškalo napisani su prema strukturi njihovih stranica i
  testirani na primjerima odgovora (`tests/fixtures`), ali **nisu provjereni na živim
  stranicama** jer iz okruženja u kojem je aplikacija napravljena nije bilo pristupa tim
  portalima. Ako portal promijeni stranicu, prilagodi `afterbuy/sources/*.py`.
- Njuškalo ima anti-bot zaštitu i može vraćati HTTP 403 – greške se vide u tablici
  "Zadnja pokretanja", a bot nastavlja s ostalim izvorima.
- Poštuj uvjete korištenja portala: bot radi jednom dnevno, s pauzama između zahtjeva.
- Procjena je samo procjena – prije kupnje uvijek provjeri stanje artikla i prodavača.

## Novi izvor oglasa

Napravi klasu u `afterbuy/sources/` koja nasljeđuje `Source` i implementira
`fetch_page(query, page, min_price, max_price) -> list[Listing]`, pa je dodaj u
`REGISTRY` u `afterbuy/sources/__init__.py`.

## Testovi

```bash
pip install pytest && python -m pytest
```
