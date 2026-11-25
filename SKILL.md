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
3. Cap it at about **5 searches**. Then answer with **Best picks** and the **All options**
   table capped at **5 rows** (same columns as full mode). If you did not ask for a passport,
   the visa note in Catch is **check**.
4. A points label appears only when a named card has a file and a transfer looks plausible.
   Do not claim a seat exists. If they did not ask for points, there is no points pick.
5. Add the one cash verdict (Book now, Watch, or Not enough data) and "this is not a forecast".
   Offer a deep dive for fee lines, visa sources, award links, and booking steps. No next-steps
   block in quick mode. Never book or transfer.

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
3. If they said fixed, still look ±3 days, but those rows are tagged **other date** and are
   never a pick. If nothing in the window was cheaper, say that in one line.
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

Use this only when you are comparing fares. If they asked for a watch, a ratio, whether to
wait, or how flexible to be, answer that first. Do not invent a table to fill the shape.
Sample numbers in `docs/example.json` are fiction. Do not copy them.

**1. Best picks.** Up to three lines. Use a label only when an option earns it:

- **Cheapest:** lowest true total that is allowed to be a pick.
- **Best trip:** fastest or fewest stops when the extra cost is small.
- **Best points value (check seat):** only if points were compared and a transfer may beat
  cash. No points asked means no points pick. This is not the cash verdict. Never claim a
  seat you did not see.

Fewer than three is fine. Other dates are not picks when the user said **fixed**. A split
ticket is not **Cheapest** unless they accepted a self-transfer.

**2. All options.** One table, sorted by cash still to pay (award taxes for a points row).
Cash, points, other dates, other airports, split tickets, and other cabins go here, each
tagged in the Option cell (`cash`, `points`, `other date`, `other airport`, `split ticket`,
`other cabin`). Six columns only:

| Option | Pay with | True total | vs cheapest | Trip (time, stops) | Catch |
|---|---|---|---|---|---|

Every number ends with a source ref `[n]`. Mark unverified figures **(unverified)**. Cap at
10 rows, then `…and N more`. Quick mode caps at 5. **vs cheapest** is against the lowest true
total in the table, including rows that are not picks. A split ticket's Catch says
**unprotected self-transfer**, plus the visa note. If no other date was cheaper, one sentence
under the table says so. Mention better award space on a nearby date only if you checked it.

**3. Next steps** (full mode only), for the picks: where to book a cash fare, or for points
the link from `awards/links.yaml`, the amount, the wait, and "I will not transfer or book
until you say so."

**4. Sources.** A numbered list: site or tool, URL, and the time you read it.

### Cash verdict

Every fare answer has exactly one of these. It is not the points pick.

Quote Google's own words when the page has them ("prices are currently low", "prices are
currently typical", "unlikely to drop", "likely to increase", "less than usual", and the
same kind of line). Add Google's caveat that future prices may not behave as expected. Do
not score the graph yourself.

The only history this project owns is `history.jsonl` and `watch.py`. Always say how many
observations that route has and the first-seen date. Fewer than 5 observations, or a span
under 7 days, is **not enough history**. Do not print min, median, or a percentile then.

- **Book now** when Google says low, less than usual, unlikely to drop, or likely to
  increase, or when the local log has enough history and the latest fare is a new low.
- **Watch** when Google says typical or the signals are mixed. Offer `watch.py`.
- **Not enough data** when there is no Google insight and the local log is thin.

Give the reason, then "this is not a forecast". Do not invent a Google sentence. If the
insight is missing, say so and point at the Price insights panel. A Kayak line or a
Skyscanner month grid is not this verdict.

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
- [ ] Fare answers start with Best picks (only labels that were earned), then one options table
- [ ] Other dates are inside that table; if none were cheaper, one sentence says so. Fixed dates are never a pick
- [ ] A split ticket's Catch says unprotected self-transfer, and it is not Cheapest unless they accepted that
- [ ] Award link or programme URL, plus the 30-second checklist, if a points pick was made
- [ ] Exactly one cash verdict, Book now, Watch, or Not enough data, with the reason and "this is not a forecast"
- [ ] Nothing was booked, paid, or transferred
