---
name: flight-points-optimiser
description: Find the cheapest way to fly from anywhere, paying cash or with transferable credit-card points and airline miles, without paid flight APIs. Use when the user wants the cheapest flight between two cities (or "anywhere"), wants to know whether to pay cash or transfer card points / air miles, asks for flexible-date or nearby-airport alternatives, or wants a price-watch alert on a route.
---

# Flight Points Optimiser

Find the cheapest way to fly, cash or transferable points, from free sources only. Never book,
pay, or transfer points unless the user agrees to that exact action. Never invent a fare, fee,
ratio, visa rule, or past price. There is no default country, passport, or home city.
`cards/india.yaml` is one country file, not a default route.

`search.py`, `history.py`, and `watch.py` are an optional unofficial scraper. They will break.
The skill works with a built-in flight search or a browser (Google Flights, Skyscanner, Kayak,
the airline's site) and does not need those scripts.

## Quick mode

Use this for a simple ask ("cheap flight to X"). A weaker agent can stop here.

1. Ask only what is missing, in one message: dates and flexibility (fixed, ±1 day, ±3 days,
   ±1 week, any time in a month, or weekends only; ask the return separately), and passengers.
   Ask about cards only if they want points compared. Do not interview them about bags, seats,
   or passports unless they bring those up.
2. If you cannot ask, search ±3 days and say so. Exact dates only if they say **fixed**.
3. Cap it at about **5 searches**. Cash top 3, each with a true total (base plus any bag or
   seat fee you actually found; unknown stays unknown) and a visa flag: OK, needs X, or check.
   If you did not ask for a passport, the flag is **check**.
4. One line on points: if `cards/<country>.yaml` matches a card they named, say whether a
   transfer looks plausibly better than cash. Do not claim a seat exists. Otherwise say points
   were not compared.
5. Offer a deep dive (full mode) for fee lines, visa sources, award links, other dates, and
   booking steps. Never book or transfer in quick mode.

## Full mode

### Hard rules

1. Never book, pay, or transfer without an explicit yes for that action. Transfers are almost
   always irreversible.
2. Every fare, fee, tax, ratio, and visa statement cites a source and a time. Blogs and memory
   are **unverified**. Unknown stays unknown, never zero and never a guess.
3. Do not treat a mileage chart as award space. Most agents cannot log in to partner sites.
   Say "not checked" unless you saw the seat, and hand the user the checks in the award section.
4. Prices move. Tell them to re-check at booking.
5. Bag, seat, card-surcharge, and booking fees come from the airline's own fee page or the
   fare brand at checkout. `fees/` is a few dated snapshots, not a complete table.
6. Visa and transit rules come from an official immigration or embassy page, or the IATA
   Travel Centre / an airline Timatic tool. No default passport.

### Inputs

Ask once, in one message, for anything missing. Defaults only where noted.

| Input | Notes |
|---|---|
| Origin / destination | City or IATA. Destination may be a region or **anywhere**. No assumed home airport. |
| Dates and flexibility | Always ask. Choices: fixed, ±1 day, ±3 days, ±1 week, a whole month, weekends only. Ask the return separately. Exact dates only if they say fixed. If you cannot ask, use ±3 days and say so. |
| Cabin / passengers | Cabin defaults to economy. Passengers default to 1 adult. |
| Currency | Ask if they don't name one. Do not assume a country. |
| Bags, seats, changes | Ask once in full mode: cabin bag or checked count and weight; any seat / together / extra legroom; whether free changes or refunds matter. |
| Passports | Every traveller's nationality, plus visas or residence permits they already hold. Examples of documents, not a default: a US visa, a Schengen visa, a Canadian eTA. |
| Cards | Issuer, product, and balance, only if comparing points. Card-issuing country picks `cards/<country>.yaml`. |

### Search

1. Built-in flight search, then a browser: Google Flights date grid and price graph, Skyscanner
   month view, Kayak, the airline site. `python search.py ORIG DEST DATE --currency XXX --flex N`
   is optional. `--flex` is 0–7 and shifts the return with the departure.
2. Scan the flexibility they chose. For a month, weekends only, or anything wider than a week,
   read a date grid first and fully price only the named date plus a few cheap samples (about
   7–10 queries per origin, not every day).
3. If they said fixed, the recommendation stays on those dates. Still look ±3 days only to fill
   the Alternative dates table, labelled as outside the fixed dates.
4. Also check a nearby airport or a positioning hop when it is likely to matter. Name the
   self-transfer risks: no protection, bag re-check, and a possible entry visa. That is not a
   normal connection.
5. **Anywhere:** shortlist 5–10 places from an explore map, then search those properly.

### True total

Rank by base fare plus the bag, seat, surcharge, and booking fees this traveller would pay.
Show each line. Flag a basic fare whose headline omits a bag or seat they need, and prefer a
bundled brand when the bundle is cheaper. Compare points with that true total, not the headline.

### Visas

For every layover and the destination: airside transit without a visa, a transit visa, whether
a self-transfer needs an entry visa, and destination entry (visa, eTA, ESTA, ETIAS, ETA, or
similar; passport validity; onward ticket). Flag **OK**, **needs X**, or **check**. Drop or
demote an option that needs a visa they cannot realistically get, and say why. Do not drop a
**check** row; put it below confirmed ones.

### Points

Load `cards/<country>.yaml`. If the country or card is missing, or `last_checked` is older than
about 60 days, or `verified` is false, re-read the issuer's page and label the figure
unverified. Do not copy another country's programme.

`points_needed = ceil(award_miles × a / b)` for ratio `a:b`, rounded to that bank's increment.
Value per point uses the true cash total minus award taxes. Say if the comparison is incomplete.

### Award check

You usually cannot log in. Never say saver space exists unless you saw it on a page that does
not require a login.

1. Build a link from `awards/links.yaml` when that programme has a prefilled template. If
   `supports_prefill` is false, give the programme's award-search home URL and say the user
   must enter the route. Templates are dated; if `last_checked` is old, say so.
2. Hand them a 30-second check: open the link, confirm saver (not only standard) space on
   the dates and cabin, note taxes and surcharges, and reject a mixed-cabin itinerary unless
   they accept it. Partners that need a login get the same checklist and the words "not checked".
3. Free public tools (airline award calendars, seats.aero or similar free tiers) are leads.
   Name the login wall and the limit. Do not treat them as proof.

### Answer

One ranked table, cheapest true total first: option, how they pay, base, fee lines, true
total, value per point, duration, stops, visa flag, caveat, source. Sample numbers in
`docs/example.json` are fiction. Do not reuse them.

Then an **Alternative dates** table: depart, return, cheapest true total, saving versus the
requested dates in money and percent, airline and stops, trade-off (weekday, red-eye, longer
trip). Top 3–5 cheaper pairs, or one sentence that none were cheaper. Mention better award
space on a nearby date only if it was actually checked.

Then steps for the top 1–3: where to book, and for points the link, the amount, the expected
wait, and "I will not transfer or book until you say so."

Then non-date alternatives: other airports, open-jaw, rail plus air, other cabins.

### Buy now or wait?

A hint, not a forecast. Use only a Google price-history graph extracted from the search
response, the on-page "prices are currently low/typical/high" sentence, the low/high pair
beside that graph, the local log (`python history.py ORIG DEST DATE`), and days until
departure as a general pattern. Google's word and a percentile of the graph can disagree;
report both and the number of points. If the graph is missing, say so and point them at the
Price insights panel in the browser. Do not invent past prices. Kayak advice and a Skyscanner
month grid are not a history of this date. State how thin the evidence is.

### Price watch

Confirm route, dates, flexibility, cabin, passengers, currency, optional threshold, schedule,
and a stop date. Store the lowest price and alert only on a new low or a fare at or below the
threshold, not on every run. `python watch.py ORIG DEST DATE --currency XXX --threshold N`
does that with cron (exit 2 means alert, exit 0 after the departure date). The first run only
records a baseline unless the fare is already under the threshold. Never book.

### Output checklist

- [ ] Quick mode stayed within one question and about 5 searches, or full mode was requested
- [ ] Flexibility was asked, or the ±3 day default was stated because you could not ask
- [ ] True totals show fee lines or say unknown; basic fares that hide fees are flagged
- [ ] Visa flag is OK, needs X, or check, with a source when it is not check
- [ ] Points use a card file or live research, and award space is "not checked" unless seen
- [ ] Award link or programme URL, plus the 30-second checklist, if points were recommended
- [ ] Alternative dates table, or a sentence that none were cheaper
- [ ] Buy-or-wait uses real evidence only and says it is not a forecast
- [ ] Nothing was booked, paid, or transferred
