---
name: flight-points-optimiser
description: Find the cheapest way to fly from anywhere, paying cash or with transferable credit-card points and airline miles, without paid flight APIs. Use when the user wants the cheapest flight between two cities (or "anywhere"), wants to know whether to pay cash or transfer card points / air miles, asks for flexible-date or nearby-airport alternatives, or wants a price-watch alert on a route.
---

# Flight Points Optimiser

Find the cheapest way to fly between two places, comparing cash fares with award tickets booked
by transferring credit-card points or using airline miles the user already holds, then give a
ranked answer with exact transfer and booking steps. Uses free sources only (your flight search
tool, Google Flights, Skyscanner, Kayak, airline websites, and the bundled `search.py`).

Works from any origin, in the user's local currency (or a currency they name). Card-transfer
data lives in `cards/<country>.yaml` (for example `cards/india.yaml`). If their country or card
has no file yet, research the issuer's official page live and label every figure **unverified**.

Files in this skill:
- `cards/`: per-country card -> airline/hotel transfer tables (ratios, caps, transfer times,
  sources, `last_checked`, `verified`). See `cards/README.md`.
- `search.py`: optional Google Flights helper (free `fast-flights` library; supports `--currency`).

## Hard rules (read before doing anything)

1. **Never book, pay, or transfer points without the user's explicit go-ahead** for that exact
   action. Transfers are almost always irreversible; points cannot come back.
2. **Never invent fares, award prices, taxes, or ratios.** Every number in your answer must
   carry its source (tool name, site + URL, or a `cards/` entry) and the time you read it.
3. If a number comes from an entry with `verified: false`, a blog, or memory, label it
   **unverified**. If you can't find a number, say so. Don't estimate it silently.
4. **Award availability must be checked on the partner programme's own site** (or the airline's
   award search) before you recommend a transfer. Never assume a seat exists because a chart
   price exists.
5. Prices change by the minute. Tell the user to re-check the fare at the moment of booking.

## Inputs

Collect these. Ask for anything missing in one short message; use sensible defaults only
where noted.

| Input | Notes |
|---|---|
| Origin | City or IATA code. Default: the user's home airport if you know it. |
| Destination | City/IATA code, a region ("Europe", "Southeast Asia"), or **"anywhere"**. |
| Dates | Departure (and return, or one-way). |
| Flexibility | E.g. "±3 days", "any weekend in March", "fixed". Default ±0 if not given. |
| Cabin | economy / premium-economy / business / first. Default economy. |
| Passengers | Adults, children, infants. Default 1 adult. |
| Currency | The user's local currency, or one they name (ISO 4217, e.g. USD, EUR, GBP, INR, JPY). If unclear, ask once; otherwise use the currency implied by their location or card-issuing country. Pass it to `search.py --currency` and quote every cash price in that currency. |
| Cards and balances | Which cards they hold (issuer and product, e.g. Chase Sapphire Reserve, HDFC Infinia, Amex UK Platinum) and current point balances. Also any airline miles already held. **Ask if not given**; without these, do a cash-only answer and say points were not compared. |
| Card-issuing country | Needed to pick the right `cards/<country>.yaml`. Ask if it is not obvious from the cards. |
| Constraints | Max stops, preferred/avoided airlines, baggage, visa limits (transit visas matter for self-transfer), latest arrival, budget. |

## Step 0: Check that the card data is fresh

Load the card file for the user's card-issuing country, if one exists (`cards/india.yaml`,
`cards/us.yaml`, and so on; see `cards/README.md`). For each card the user holds:

- If **there is no file for that country**, or the card is not in the file, say so, and
  **research transfer partners from the issuer's official page** before using any ratio.
  Mark everything you find **unverified** until it is confirmed on that official page (or by
  the user reading the ratio in their bank's transfer portal). Do not copy ratios from memory
  or from a different country's programme (US Amex Membership Rewards is not Amex India).
- If `last_checked` (on the card or a partner you plan to use) is **more than ~60 days before
  today**, warn: "The <card> ratios in cards/<file> were last checked on <date>; issuers change
  partners and ratios often. I'll re-verify before recommending a transfer." Then re-check the
  issuer's official page (the `source_url`) and use the fresh number, citing it.
- Treat every `verified: false` ratio as a lead. Before telling the user to transfer, confirm it
  on the official page or ask them to confirm the ratio shown in their bank's transfer portal.

## Step 1: Search cash fares

Search in this order, and record the source and time of every price. Use the chosen currency
throughout.

1. **Your flight search tool** (the agent's built-in flight search, if you have one). Search the
   exact dates first, then the flexible dates and alternate airports (Step 2).
2. **Fallbacks** if there is no built-in tool, or it fails or returns thin results:
   - `python search.py <ORIGIN> <DEST> <YYYY-MM-DD> [--return YYYY-MM-DD] [--cabin business] [--adults N] [--flex 3] [--airports AAA,BBB] [--currency USD] --json-only`
     (Google Flights via the free `fast-flights` scraper; `--currency` is passed through to
     Google Flights. The scraper may break or get rate-limited. Its round-trip results are less
     complete than one-way, so cross-check round trips.)
   - **Google Flights** in a browser (google.com/travel/flights): use the Date grid / Price graph
     for flexible dates and the "Explore" map for "anywhere". Set the display currency.
   - **Skyscanner** in a browser: "Whole month" / "Cheapest month" views and "Everywhere" as the
     destination for "anywhere".
   - **Kayak** in a browser: fare calendar and "Explore" / flexible-date views, as a second
     opinion when Google Flights and Skyscanner disagree or look thin.
   - The **airline's own site** for the final price (often different from OTAs, and needed for
     fare-rule details).
3. For **"anywhere"**: use Google Flights Explore, Skyscanner "Everywhere", or Kayak Explore
   from the origin for the date range, shortlist the 5-10 cheapest destinations that fit the
   user's constraints, then search each properly.

Capture for each option: price (total for all passengers, in the chosen currency), airline(s),
flight numbers if shown, stops and layover airports, total travel time, baggage included, fare
type, source, timestamp.

Not a fare source: Firecrawl Alexandria's flight page (https://alexandria.firecrawl.dev/go/flights)
offers **live flight status** (delays, cancellations, ground stops, airport security lines)
through Firecrawl. It needs a Firecrawl account or API key with Alexandria enabled, and it does
not return fares. Use it only, if the user has it connected, to check disruptions on a shortlisted
flight or a tight self-transfer connection.

## Step 2: Flexible dates and alternate airports

Try these and keep anything materially cheaper (a useful rule of thumb: more than about 10% or a
clearly meaningful amount per person in the chosen currency) as an alternative:

- **±3 days** around each date (`search.py --flex 3`, or the Google Flights / Kayak date grid).
  Note day-of-week patterns: midweek departures are often cheaper than Friday or Sunday;
  red-eyes are often cheaper than daytime flights.
- **Calendar / month view** on Skyscanner, Google Flights or Kayak when the user is flexible by
  weeks.
- **Nearby / alternate origins and destinations.** Always look at other airports serving the
  same metro area, and at a positioning hop to a better-connected hub, adding the positioning
  flight's price and time and a buffer. Worked examples (adapt to the user's actual cities):
  - **India:** from Bengaluru compare BLR with MAA (Chennai), COK (Kochi), HYD (Hyderabad), plus
    positioning to the big hubs **DEL / BOM**, which often have more nonstop international
    options and sales.
  - **United States:** secondary airports in the same metro, e.g. **OAK / SJC vs SFO**, EWR / LGA
    vs JFK, BUR / SNA / ONT vs LAX, BWI / IAD vs DCA, FLL vs MIA. Check whether a ground
    transfer (BART, AirTrain, FlyAway) still beats the fare gap.
  - **Europe:** low-cost bases and alternate airports (LTN / STN / LGW vs LHR, ORY vs CDG,
    CIA / CIA-area vs FCO, BER vs the older city airports where relevant) and **rail plus
    air**: a cheap flight into a nearby city plus a high-speed train (Thalys/Eurostar, TGV,
    AVE, ICE, Italo) can beat a last-leg fare. Say when tickets are separate and unprotected.
  - **Gulf and South-East Asia hubs:** compare through-fares with two tickets via DXB, AUH,
    DOH, BAH, MCT, or SIN, KUL, BKK, HKG. See self-transfer warnings below.
- **Open-jaw:** fly into one city and out of another when it saves money or backtracking.
- **Separate tickets via hubs:** **self-transfer risks must be stated**: no protection if the
  first flight is late (missed connection = a new ticket), you must usually re-check bags, and
  you may need a transit or entry visa for the hub (check the user's passport rules; some
  nationalities need a visa even to airside-transit in places such as the UK, Canada, the US,
  or certain Schengen airports). Leave at least 3-4 hours between flights, more for
  international-to-international with bags or a terminal change. Never present a self-transfer
  as equivalent to a protected connection.
- **Cabin swaps:** check premium economy vs economy and business on points; the points gap is
  often smaller than the cash gap.

## Step 3: Compare against points

For each card the user holds, using the matching `cards/<country>.yaml` file (or live official
research if there is no file):

1. List the **transfer partners that can actually book this route**: the airline itself,
   alliance partners (Star Alliance, oneworld, SkyTeam), or other bookable partners. E.g. a
   United flight may be bookable with United MileagePlus and often via other Star Alliance
   programmes (Aeroplan, Avianca LifeMiles, Air India's Maharaja Club, and so on). Verify
   partner bookability on the programme's site. Do not assume a US, UK or India transfer list
   applies to another region.
2. For each candidate programme, **find the award price and availability on the programme's
   own website** (log-in may be needed; ask the user to check if you cannot). Record the miles
   needed, the cash taxes and fuel surcharges, and the source and time. Award charts and
   dynamic pricing change: never use a remembered price as fact.
3. Compute, in the chosen currency:
   - `points_needed = ceil(award_miles × a / b)` for ratio `a:b` (card points : miles), rounded
     up to the bank's transfer increment (minimums and multiples are in the card file; e.g.
     HDFC: multiples of 100; Axis: minimum 500 EDGE Miles). Subtract any miles the user already
     holds in that programme.
   - `cash_saved = cash_fare - award_taxes_and_surcharges` (same passengers, same or similar
     itinerary; say if the itinerary differs).
   - `value_per_point = cash_saved / points_needed` in the chosen currency (or its minor units).
   - Compare with the card's **fixed-value alternative** when one exists (statement credit,
     travel portal, or a fixed cents-per-point rate). If transferring beats it by little, prefer
     the simpler, reversible-until-booked option.
4. Check and report **constraints**: monthly/annual caps and group caps, minimums, transfer
   fees, **transfer time** (seats can vanish while points are in transit; prefer instant or
   one-day partners when space is scarce), linking waits, name-match rules, and recent
   devaluations or partner removals noted in the card file.
5. If the balance is short, say how short, and whether combining cards or programmes works
   (points usually cannot be pooled across banks; miles may be combinable within some airline
   families, e.g. Avios between British Airways, Qatar and other Avios programmes, under each
   programme's current rules).

## Step 4: Ranked answer

Give one table, cheapest effective cost first. Include cash and points options together.
Use the chosen currency. The rows below only show the format; **never reuse their numbers**.

| # | Option | Pay with | Total cost | Value/pt | Duration | Stops | Caveats | Source |
|---|---|---|---|---|---|---|---|---|
| 1 | LHR-JFK, Airline XX..., 16 Dec | Cash | £850 | - | 8h25m | 0 | Bag fee may be extra | Google Flights, <date time TZ> |
| 2 | LHR-JFK, Airline YY..., 16 Dec | 40,000 card pts -> 20,000 partner miles + £350 taxes | 40k pts + £350 | 1.25 pence/pt (unverified ratio) | 8h20m | 0 | Saver space must be re-checked on the partner site | partner site, <date time TZ> |

- "Total cost" for points options = points + cash taxes/fees (and transfer fees, if any).
- Mark any unverified number inline with **(unverified)**.
- Then give **exact steps for the top 1-3 picks**:
  - Cash: where to book (airline site vs OTA), fare class/brand, what to check (baggage,
    change fees, name exactly as on passport).
  - Points: (1) create or log in to the partner account and confirm the award seat is still
    there; (2) link the account in the bank portal if needed (note any waiting period);
    (3) transfer exactly N points from the portal path in the card file; (4) wait for the
    credit (expected time); (5) book the award on the partner site; (6) pay taxes with a card.
    Say clearly: "Transfers are irreversible. I won't transfer or book anything until you say so."

## Step 5: Alternatives

After the ranked table, add a short **Alternatives** section: cheaper or better options found
with other dates, airports (including positioning hops and secondary airports), open-jaw,
separate tickets (with self-transfer and visa risks), other cabins (e.g. business on points vs
economy cash), rail-plus-air, and other airlines or programmes. Give each one's saving vs the
top pick and its trade-off.

## Step 6 (optional): Price watch

If the user wants alerts, offer to set up a recurring routine (using your platform's scheduler /
routine feature) that:
- re-runs the cash search (same route, dates, flexibility, cabin, passengers, currency) on a
  schedule the user picks (e.g. daily at a local morning hour);
- stores the lowest price seen so far and its source;
- **alerts only when** the price drops below the user's threshold or a new all-time low appears
  (optionally, when award space opens on a named programme, if checkable);
- includes in each alert the new price, the previous low, source link, and timestamp;
- never books or transfers anything, and stops after the travel date or when the user says.

Confirm the route, threshold, currency and schedule with the user before creating it.

## Output checklist

- [ ] Inputs confirmed (or defaults stated), including currency
- [ ] The right `cards/<country>.yaml` loaded, or live official research done and labelled unverified
- [ ] Stale card entries (> ~60 days) flagged and re-verified
- [ ] Cash fares from your flight search tool first, then fallbacks; each with source + time
- [ ] Flexible-date and alternate-airport options checked
- [ ] Points options: partner, ratio (verified?), points needed, taxes, value per point,
      caps, fees, transfer time; award space checked on the partner's own site
- [ ] Ranked table + step-by-step instructions for the top picks
- [ ] Alternatives section
- [ ] Clear statement that nothing was booked or transferred
