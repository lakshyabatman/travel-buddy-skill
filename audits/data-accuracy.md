# Audit: data accuracy

Date: 2026-11-25 (Asia/Calcutta). Scope: every `verified: true` ratio and the verified card
terms in `cards/india.yaml`, re-checked against the cited `source_url`.

## Method

Reloaded each official URL (or PDF) and compared the stated ratio, cap or fee with the YAML.
`verified: false` rows were not re-promoted; they stay leads.

## Findings

### HDFC Infinia and Diners Club Black — verified ratios (6)

| Partner | YAML | Official source on re-check | Result |
|---|---|---|---|
| Singapore Airlines KrisFlyer | 1:1 | HDFC rewards redemption form: "Infinia / Diners … 100RP = 100 AirMiles", form labelled KrisFlyer. The same form says further partners are on SmartBuy. | Confirmed |
| Air India Maharaja Club | 2:1 | Air India's official HDFC page: Infinia / Infinia Metal 2:1, Diners Black / Black Metal 2:1, Regalia Gold 3:1. Transfer 2–4 working days, irreversible, min 100 Maharaja points in multiples of 100. | Confirmed (curl from this box failed; WebFetch succeeded) |
| Cathay Asia Miles | 2:1 | Cathay official HDFC page: Infinia "100 HDFC Bank Credit Card Reward Points = 50". | Confirmed |
| Turkish Miles&Smiles, Avianca LifeMiles, Accor ALL | 2:1 | Infinia rewards T&C PDF, effective 15 Jan 2024: "2 Reward Points will be converted to 1 Loyalty Point for Turkish Miles, Accor and Avianca Life Miles". Same clause is in the Diners Black Metal PDF. | Confirmed |

The other 16 HDFC partners stay `verified: false` (SmartBuy's live table needs a card login, and the portal did not load from this network). That marking is correct.

### HDFC card terms

- Infinia monthly cap of 1,50,000 RP for flights, hotels and airmiles: confirmed on the official Infinia product page ("1.5 lakh … per month for Flights, Hotel Bookings and airmiles") and the rewards T&C PDF.
- ₹99 redemption fee waived for Infinia and Diners Black: confirmed on the official redemption form.
- Diners Black monthly cap of 75,000 RP: the official `diners6.pdf` caps SmartBuy **flights and hotel bookings** at 75,000 RP a month. The airmiles-inclusive wording is on an official SmartBuy / Reward360 offer T&C (`offers.reward360.in/miles_transfer/bonus_offer`), which we already cite. No change to the figure; the audit notes the slightly narrower wording on the PDF.
- "Max 5 redemptions per month from 1 Feb 2026" remains `verified: false` (Business Standard only). Correct.

### Axis Atlas — all 28 listed partners

Re-parsed the official Travel EDGE terms page (`traveledge.axis.bank.in/travel/common/termsandcondition`) on 2026-11-25. Every Atlas ratio in `cards/india.yaml` matches the official Atlas column, including the reduced 2:1 tier (Accor, British Airways, Cathay, Finnair, Qatar, Vietnam, IndiGo BluChip) and the standard 1:2 / 1:1 Group A and B rates. Annual caps (1,50,000 total; 30,000 Group A; 1,20,000 Group B) and partner transfer times match. IOCL XTRAREWARDS 3:10 (Atlas only) matches.

### Axis Marriott — wording was too strong

**Finding:** Marriott is listed under `removed_partners` with the note "Not in the live Axis table on 2026-11-25." On re-parse, a Marriott row still appears in the conversion-ratio table (the Atlas cell in that row is 2:1, but neighbouring columns do not follow the usual card pattern). Marriott is **not** in the official Group A / Group B list (it sits in an HTML comment). Blogs date a removal to April 2026.

**Fix:** Updated the `removed_partners` note to describe this exactly, and to say: do not treat Marriott as a live partner or use that 2:1 figure until the logged-in Travel EDGE portal clearly offers it. Marriott was not added back as a live partner.

### Amex India MR

All seven partner ratios remain `verified: false`. The official transfer table is behind a login; the public global URL served US data. No verified ratio was claimed, so none failed a re-check. Correct.

## Verdict

Verified figures that we use for transfers re-checked successfully, with the one Marriott wording fix above. Unverified rows stay unverified.
