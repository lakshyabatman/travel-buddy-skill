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
  sources, `last_checked`, `verified`). See `cards/README.md`. One file per issuing country.
  `cards/india.yaml` is the country file shipped in v1, not a default route, currency, or passport.
- `fees/`: optional dated snapshots of official airline fee pages (`fees/README.md`,
  `schemas/fees.schema.json`). A missing or stale file means "look it up", not "guess".
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
6. **Never invent bag, seat, payment, booking, or other add-on fees.** For each shortlisted
   option, read the airline's official fee page or the fare-brand details shown at checkout,
   and cite the source and time. A third-party site or a remembered fee is **unverified**.
   If you cannot find a fee, say it is **unknown**. Do not fill the gap with a guess, and do
   not treat an unknown fee as zero. `fees/*.yaml` is a few dated official snapshots, not a
   complete table and not a default airline.
7. **Never invent visa or transit rules.** For every layover and the destination, cite an
   official government immigration or embassy page, or the IATA Travel Centre / a Timatic-based
   tool the airline itself exposes. If you are unsure, mark it **unverified** and tell the user
   to confirm with the airline or the embassy. Never present a visa answer as certain without
   an official source. There is no default passport.

## Inputs

Collect these. Ask for anything missing in one short message; use sensible defaults only
where noted.

| Input | Notes |
|---|---|
| Origin | City or IATA code. Default: the user's home airport if you know it. |
| Destination | City/IATA code, a region ("Europe", "Southeast Asia"), or **"anywhere"**. |
| Dates | Departure (and return, or one-way). Naming a date does **not** mean the date is fixed. |
| Flexibility | **Always ask. Never a silent default of "exact dates".** Offer: fixed, ±1 day, ±3 days, ±1 week, any time in a given month, or weekends only. On a round trip, ask about the **return separately**. Search exact dates only if the user says **fixed**. If you cannot ask (an automated run, or any turn with no way to get an answer), use **±3 days** and say so. If they already stated the flexibility, use that and do not ask again. |
| Cabin | economy / premium-economy / business / first. Default economy. |
| Passengers | Adults, children, infants. Default 1 adult. |
| Currency | The currency they want prices quoted in (ISO 4217). If they don't name one, ask once; do not assume a country. Pass it to `search.py --currency` and quote every cash price in that currency. |
| Bags | **Ask once.** Cabin bag only, or how many checked bags and the weight of each. Do not assume "no checked bag" or any airline's allowance. |
| Seats | **Ask once.** Any seat, sit together (for a group), or extra legroom. |
| Changes and refunds | **Ask once** whether they care about free changes or refunds. If they do, a cheap fare that cannot be changed is not automatically the winner. |
| Passports and visas held | **Ask for every traveller** if they might differ: passport nationality, plus any residence permit or visa they already hold. Examples of documents that can change a transit rule, not a default nationality: a US visa, a UK visa, a Schengen visa, a Canadian eTA, an Australian ETA, an Indian e-visa, a Gulf residence permit. There is **no default passport**. |
| Cards and balances | Which cards they hold (issuer and product) and current point balances. Also any airline miles already held. **Ask if not given**; without these, do a cash-only answer and say points were not compared. Examples from different regions, not a home country: a US Ultimate Rewards card, a UK Membership Rewards card, an Indian reward-points card, a Singapore miles card, a Brazilian or Gulf issuer's card. |
| Card-issuing country | Needed to pick the right `cards/<country>.yaml`. Ask if it is not obvious from the cards. Do not assume the departure country issues the card. |
| Constraints | Max stops, preferred or avoided airlines, latest arrival, budget. Bags, seats, changes, and passports are the rows above, not a silent extra. |

## Ask about date flexibility first

Do this before any fare search. **Always ask whether the dates are flexible and by how much.**
Do not treat a named date as fixed, and do not quietly search only that date.

Ask in the same short message as the other missing inputs. Offer these choices, and on a round
trip ask the same question **again for the return** (the outbound can be fixed while the return
moves, or the other way around):

- **fixed** (these dates only)
- **±1 day**
- **±3 days**
- **±1 week**
- **any time in a given month**
- **weekends only**

**Only search exact dates alone when the user says fixed.** If they already said how flexible
they are ("±3 days", "any weekend in March", "dates are fixed"), do not ask again. If they
gave one window for a round trip and it clearly applies to both ends, use it for both and say
so. If only the departure flexibility is clear, still ask about the return.

If you **cannot ask** (an automated run, a price-watch re-run, or any other case with no reply
channel), do not assume the dates are fixed. **Default to ±3 days and say so** in the answer,
for example: "You didn't specify flexibility and I couldn't ask, so I searched ±3 days around
the dates."

The same limit applies to bags, seats, changes, and passports. If you cannot ask, do **not**
invent a nationality, a checked-bag count, or a fee. Rank on the base fare only, label every
missing fee **unknown**, put **check** in the visa column, and say the true total is incomplete.

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
   dates they named and the flexibility window from "Ask about date flexibility first". If they
   said fixed, the recommendation uses those exact dates; Step 2 still scans ±3 days only to
   fill the Alternative dates table. Then alternate airports (Step 2).
2. **Fallbacks** if there is no built-in tool, or it fails or returns thin results:
   - `python search.py <ORIGIN> <DEST> <YYYY-MM-DD> [--return YYYY-MM-DD] [--cabin business] [--adults N] [--flex N] [--airports AAA,BBB] [--currency USD] --json-only`
     (Google Flights via the free `fast-flights` scraper; `--currency` is passed through to
     Google Flights. `--flex N` scans ±N days around departure and shifts the return by the
     same number of days. **N must be 0–7**; a larger value is rejected. Use `--flex 1`,
     `--flex 3`, or `--flex 7` for ±1 day, ±3 days, and ±1 week. If the return window differs
     from the departure window, do not rely on `--flex` alone. The scraper may break or get
     rate-limited. Its round-trip results are less complete than one-way, so cross-check
     round trips.)
   - **Google Flights** in a browser (google.com/travel/flights): use the **Date grid** and
     **Price graph** to scan the flexibility window, and the "Explore" map for "anywhere".
     Set the display currency.
   - **Skyscanner** in a browser: **"Whole month" / "Cheapest month"** when the window is a
     month, ±1 week, or weekends only, and "Everywhere" as the destination for "anywhere".
   - **Kayak** in a browser: fare calendar and "Explore" / flexible-date views, as a second
     opinion when Google Flights and Skyscanner disagree or look thin.
   - The **airline's own site** for the final price (often different from OTAs, and needed for
     fare-rule details).
3. For **"anywhere"**: use Google Flights Explore, Skyscanner "Everywhere", or Kayak Explore
   from the origin for the date range, shortlist the 5-10 cheapest destinations that fit the
   user's constraints, then search each properly.
4. **Cap the number of searches.** A ±1 day or ±3 day window can be scanned directly. A week
   is as wide as `search.py --flex` goes (`--flex 7`). For a whole month, weekends only, or
   any wider window, read the Google Flights date grid / price graph or the Skyscanner month
   view first, then run full fare searches only for the named dates plus the cheapest samples
   (about 7–10 dated queries per origin, not every day). Say which days you sampled. On a
   round trip with different departure and return flexibility, sample pairs instead of shifting
   both ends by the same amount.

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

- **The date window they chose** (or ±3 days if you could not ask, stated as a default). Scan it
  with `search.py --flex N` (N is 0–7), the Google Flights date grid and price graph, and, when
  the window is a month, a week, or weekends only, the Skyscanner month view. Sample a wide
  window instead of querying every day (see Step 1). Note day-of-week patterns: midweek
  departures are often cheaper than Friday or Sunday; red-eyes are often cheaper than daytime
  flights; a cheaper return can make the trip longer. These comparisons fill the **Alternative
  dates** table in Step 6.
- If they said **fixed**, the ranked recommendation stays on the exact dates. Still scan ±3 days
  around those dates so the Alternative dates table can show cheaper pairs, or say that none
  were cheaper. Label every other date as outside the fixed dates. Do not swap the recommended
  itinerary onto another day unless they then agree.
- **Nearby / alternate origins and destinations.** Always look at other airports serving the
  same metro area, and at a positioning hop to a better-connected hub, adding the positioning
  flight's price and time and a buffer. Use the user's actual cities. Examples from several
  regions (none of these is a default origin):
  - **Americas:** OAK / SJC vs SFO, EWR / LGA vs JFK, BUR / SNA / ONT vs LAX, BWI / IAD vs DCA,
    FLL vs MIA, YYZ vs YTZ, MEX vs NLU, GRU vs CGH / VCP, EZE vs AEP, BOG, SCL. Check whether
    the ground transfer still beats the fare gap.
  - **Europe:** LTN / STN / LGW vs LHR, ORY vs CDG, and **rail plus air** (a cheap flight into a
    nearby city plus Eurostar, TGV, AVE, or ICE). Say when those tickets are separate and
    unprotected.
  - **Africa:** JNB vs HLA, CPT, NBO, ADD, CAI, and other hubs when a connection beats a thin
    nonstop from a smaller city.
  - **Asia, Gulf, and Oceania:** DEL / BOM (one pair of hubs among many, not a default), SIN,
    KUL, BKK, HKG, DXB, AUH, DOH, SYD vs MEL, AKL. Compare a through-fare with two tickets via
    a hub. See self-transfer warnings below.
- **Open-jaw:** fly into one city and out of another when it saves money or backtracking.
- **Separate tickets via hubs:** **self-transfer risks must be stated**: no protection if the
  first flight is late (missed connection = a new ticket), you must usually re-check bags, and
  you may need a transit or entry visa for the hub. That depends on the traveller's passport
  and on whether they stay airside; do not assume any hub is visa-free or visa-required. Step 5
  checks it from an official source. Leave at least 3-4 hours between flights, more for
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
   programmes (Aeroplan, Avianca LifeMiles, or another Star Alliance programme that actually
   sells the seat). Verify partner bookability on the programme's site. Do not assume one
   country's transfer list applies to a card issued somewhere else.
2. For each candidate programme, **find the award price and availability on the programme's
   own website** (log-in may be needed; ask the user to check if you cannot). Record the miles
   needed, the cash taxes and fuel surcharges, and the source and time. Award charts and
   dynamic pricing change: never use a remembered price as fact.
3. Compute, in the chosen currency:
   - `points_needed = ceil(award_miles × a / b)` for ratio `a:b` (card points : miles), rounded
     up to the bank's transfer increment (minimums and multiples are in that card's file; do not
     reuse another issuer's increment). Subtract any miles the user already
     holds in that programme.
   - `cash_saved = true_total_cash - award_taxes_and_surcharges` (same passengers, same or similar
     itinerary; say if the itinerary differs). `true_total_cash` is the Step 4 total, not the
     headline fare. If a fee on either side is unknown, say the comparison is incomplete.
   - `value_per_point = cash_saved / points_needed` in the chosen currency (or its minor units).
   - Compare with the card's **fixed-value alternative** when one exists (statement credit,
     travel portal, or a fixed value-per-point rate). If transferring beats it by little, prefer
     the simpler, reversible-until-booked option.
4. Check and report **constraints**: monthly/annual caps and group caps, minimums, transfer
   fees, **transfer time** (seats can vanish while points are in transit; prefer instant or
   one-day partners when space is scarce), linking waits, name-match rules, and recent
   devaluations or partner removals noted in the card file.
5. If the balance is short, say how short, and whether combining cards or programmes works
   (points usually cannot be pooled across banks; miles may be combinable within some airline
   families, e.g. Avios between British Airways, Qatar and other Avios programmes, under each
   programme's current rules).

## Step 4: True total cost

Do this for every shortlisted cash option before you rank. The headline fare is not the price.

1. Use the bag, seat, and change answers from Inputs. If any of those is missing and you can
   still ask, ask once. If you cannot ask, leave those fee lines as **unknown**.
2. For each option, add the fees this traveller would actually pay:
   - checked bags and any extra cabin bag, at the weight they named
   - seat selection (any seat / together / extra legroom)
   - payment or card surcharges
   - booking fees and other mandatory extras (airport check-in, under-seat-only upgrades)
3. Read each figure on the **airline's official fee page** or on the **fare-brand details at
   checkout**. Cite the page and the time. You may start from `fees/<airline>.yaml` when the
   snapshot matches that airline and market and `last_checked` is within about 60 days, then
   confirm it is still the current page. A different market, a stale file, a blog, or a memory
   is **unverified** or **unknown**, never a silent number.
4. **Rank by the true total** = base fare + those fee lines, in the chosen currency. Show the
   base fare and each fee line, not only the sum. If a fee is unknown, show the partial total
   and say it is incomplete. Do not pretend the unknown line is zero.
5. **Flag budget carriers** (and any basic fare) where the headline omits bags or seats the
   user needs. Compare fare brands on the same airline: if a standard brand that bundles the
   bag and seat is cheaper than basic-plus-fees, recommend the bundle and show both totals.
6. Award taxes and carrier surcharges count in the points true cost as well. A points option
   is "points + cash taxes and fees", not "points" alone.

## Step 5: Visas and transit

Do this for every option you might recommend, including self-transfers and open-jaws. There is
no default passport and no default "safe" hub.

1. Use the passport nationality, and any residence permit or visa already held, for **each**
   traveller. If two travellers differ, check both and keep the stricter result.
2. For every layover airport and for the destination, answer:
   - Is **airside transit** allowed without a visa?
   - Is a **transit visa** required?
   - Does a **self-transfer or separate ticket** (landside entry, baggage re-check, or a change
     of airport) need an **entry visa** the airside connection would not?
   - What does **destination entry** require (visa, eTA, ESTA, ETIAS, ETA, or a similar
     authorisation; passport validity; onward ticket)?
3. Sources, in this order: the destination or transit country's **official immigration or
   embassy page**, then the **IATA Travel Centre** or a **Timatic-based** tool that an airline
   exposes to the public. Cite the URL and the time. If those disagree or you cannot open them,
   mark the cell **unverified** and tell the user to confirm with the airline or the embassy.
   Never fill a visa cell from memory.
4. In the ranked table, set **Visa / transit** to one of:
   - **OK** — an official source says this traveller can transit and enter as planned
   - **needs X** — name the visa or authorisation (for example "needs a transit visa for the
     hub" or "needs an ETA before departure")
   - **check** — you could not confirm it
5. **Drop or demote** an option that needs a visa or authorisation the traveller cannot
   realistically get before departure (no existing visa, a long lead time, or a landside
   self-transfer they cannot enter). Say why, and keep a one-line note so they can see what
   was removed. Do not drop an option merely because the cell is **check**; demote it below
   options that are **OK** and say it is unconfirmed.

## Step 6: Ranked answer

Give one table, cheapest **true total** first. Include cash and points options together.
Use the chosen currency. The rows below only show the format; **never reuse their numbers**.
The route is one illustration. The same columns are used for any region.

| # | Option | Pay with | Base | Fee lines | True total | Value/pt | Duration | Stops | Visa / transit | Caveats | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MEX-MAD, Airline XX standard, 16 Dec | Cash | MXN 5100 | Bag included; seat included | MXN 5100 | - | 11h | 1 | OK (example label only) | Example only. Standard brand beat basic-plus-fees | airline fee page, <date time TZ> |
| 2 | MEX-MAD, Airline XX basic, 16 Dec | Cash | MXN 4200 | Checked bag MXN 900; seat MXN 350 | MXN 5450 | - | 11h | 1 | OK (example label only) | Example only. Headline looks cheaper; flag it | airline fee page, <date time TZ> |
| 3 | MEX-MAD, Airline YY, 16 Dec | 40,000 card pts -> 20,000 miles + MXN 2800 taxes | n/a | Award taxes MXN 2800 | 40k pts + MXN 2800 | MXN 0.0575/pt (unverified ratio) | 10h40m | 0 | check | Example only. Re-check saver space on the partner site | partner site, <date time TZ> |

- "True total" for points = points + cash taxes, surcharges, and transfer fees.
- A basic fare whose headline omits a bag or seat the user needs is flagged in Caveats.
- Mark any unverified number inline with **(unverified)**. A visa cell is **OK** only with an
  official source. The "OK" and "check" labels in the sample are format only, not a ruling.
- If you removed an option because of a visa, say so under the table in one sentence.

**Then always an Alternative dates table**, before the booking steps. One row per depart/return
pair (on a one-way, leave Return as "—"). Columns: depart date, return date, cheapest price,
saving versus the **requested** dates (absolute and percent), airline and stops, and the
trade-off (weekday vs weekend, red-eye, longer or shorter trip, extra overnight). Show the
**top 3–5 cheaper** date options. If nothing in the window beat the requested dates, do not
invent rows: write one plain sentence, for example "No date in the ±3 day window was cheaper
than 16 Dec at MXN 5100." The rows below only show the format; **never reuse their numbers**.
Savings are against the requested dates' true total, not the headline fare.

| Depart | Return | Cheapest true total | Saving vs requested dates | Airline / stops | Trade-off |
|---|---|---|---|---|---|
| 14 Dec | — | MXN 4080 | MXN 1020 (20%) | Airline ZZ, 1 stop | Two days earlier; longer elapsed time |
| 15 Dec | — | MXN 4590 | MXN 510 (10%) | Airline XX, nonstop | Weekday; red-eye |
| 18 Dec | — | MXN 4845 | MXN 255 (5%) | Airline XX, nonstop | Two days later |

If you checked award space, say when a nearby date has space the requested date does not (or
clearly more of it), with the programme and the date you looked. If you did not check awards
off the requested dates, say that you did not.

Then give **exact steps for the top 1-3 picks**:

- Cash: where to book (airline site vs OTA), fare class/brand, what to check (baggage,
  change fees, name exactly as on passport).
- Points: (1) create or log in to the partner account and confirm the award seat is still
  there; (2) link the account in the bank portal if needed (note any waiting period);
  (3) transfer exactly N points from the portal path in the card file; (4) wait for the
  credit (expected time); (5) book the award on the partner site; (6) pay taxes with a card.
  Say clearly: "Transfers are irreversible. I won't transfer or book anything until you say so."

## Step 7: Alternatives

After the Alternative dates table, add a short **Alternatives** section for everything that is
not another date: airports (including positioning hops and secondary airports), open-jaw,
separate tickets (with self-transfer and visa risks), other cabins (e.g. business on points vs
economy cash), rail-plus-air, and other airlines or programmes. Date changes belong in the
Alternative dates table, not here. Give each option's saving vs the top pick and its trade-off.

## Step 8 (optional): Price watch

If the user wants alerts, offer to set up a recurring routine (using your platform's scheduler /
routine feature) that:
- re-runs the cash search on a schedule the user picks (e.g. daily at a local morning hour),
  using the flexibility they confirmed (or the stated ±3 day default), not a silent exact-date
  search; same route, cabin, passengers, and currency;
- stores the lowest price seen so far and its source;
- **alerts only when** the price drops below the user's threshold or a new all-time low appears
  (optionally, when award space opens on a named programme, if checkable);
- includes in each alert the new price, the previous low, source link, and timestamp;
- never books or transfers anything, and stops after the travel date or when the user says.

Confirm the route, threshold, currency and schedule with the user before creating it.

## Buy now or wait?

This is a hint, not a forecast. Never invent a past price.

Use only evidence you actually have:

1. **Google's price-history graph**, when `search.py` extracted one from the search response
   (a daily series plus, when present, the on-page sentence "prices are currently
   low/typical/high" and a low/high pair from the same block). Say how many points, the
   min, median and max, and where the latest point sits. Google's word and a percentile of
   the graph can disagree; report both. The free `fast-flights` flight list does not include
   this graph. If the response has no graph, say so.
2. **Browser fallback.** Open the same Google Flights search and read the Price insights /
   Price history panel. Do not type in numbers you did not see.
3. **The local log** (`~/.flight-points-optimiser/history.jsonl`, or `$FLIGHT_POINTS_HISTORY`).
   It only records searches made on this machine. The first run is one observation. Read it
   with `python history.py ORIG DEST DATE`.
4. **Days until departure**, as a general pattern only: fares often move more in the last
   few weeks. Say that it is general, not a rule for this route.
5. Do not treat a Kayak "advice" line or a Skyscanner month grid as a history of this date.
   A month grid compares other dates. It is not a time series.

State a confidence in the **evidence** (low if there is no graph; medium if the graph has
about 30 or more points) and end with: this is not a guaranteed forecast.

## Output checklist

- [ ] Inputs confirmed, including currency, bags, seats, and whether changes or refunds matter.
      No assumed passport. If you could not ask, missing fees are **unknown** and visas are **check**
- [ ] Date flexibility was asked (fixed, ±1 day, ±3 days, ±1 week, a whole month, or weekends
      only), and the return was asked separately on a round trip. Exact dates only if the user
      said fixed. If you could not ask, the ±3 day default is stated in the answer
- [ ] The right `cards/<country>.yaml` loaded, or live official research done and labelled unverified
- [ ] Stale card entries (> ~60 days) flagged and re-verified
- [ ] Cash fares from your flight search tool first, then fallbacks; each with source + time
- [ ] The flexibility window was scanned (`search.py --flex N`, Google Flights date grid / price
      graph, and/or Skyscanner month view). A wide window was sampled, not queried day by day
- [ ] Alternate airports (and positioning hops, where relevant) checked, using the user's cities
      rather than a default country
- [ ] True total built from official fee lines (bag, seat, surcharges, booking fees). Base fare
      and each fee shown. Unknown fees labelled unknown. Budget-carrier headlines flagged.
      Fare brands compared when a bundle is cheaper
- [ ] Visa / transit checked for every layover and the destination, from an official government
      page or IATA Travel Centre / airline Timatic tool. Column is OK / needs X / check.
      Options the traveller cannot enter or transit are dropped or demoted, with the reason
- [ ] Points options: partner, ratio (verified?), points needed, taxes, value per point against
      the true total, caps, fees, transfer time; award space checked on the partner's own site.
      Nearby dates with better award space mentioned if that was checked
- [ ] Ranked table by true total, then an Alternative dates table (top 3–5 cheaper depart/return
      pairs with absolute and percent savings, airline/stops, and trade-offs — or a plain
      sentence that none were cheaper), then step-by-step instructions for the top picks
- [ ] Alternatives section (airports, cabins, split tickets, and other non-date options)
- [ ] Buy now or wait uses only a real Google graph, the on-page label, or the local log, and says it is not a forecast. No invented history
- [ ] Clear statement that nothing was booked, paid, or transferred
