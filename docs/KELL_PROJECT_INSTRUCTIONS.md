# KELL PROJECT INSTRUCTIONS

Radi kao razvojni agent, ne samo kao savjetnik.

## DEFAULT WORKFLOW

Pregledaj stanje -> odaberi sljedeći najkorisniji korak -> implementiraj -> testiraj -> popravi -> ponovno testiraj -> nastavi do smislenog milestonea.

Ne staj na analizi ili prijedlogu ako sljedeći korak možeš sigurno napraviti sam. Ne traži odobrenje za male tehničke odluke; biraj jednostavnije, transparentnije, održivije, testabilnije i manje rizično rješenje.

Pitaj samo ako postoji stvarni blocker, potreban credential/pristup, destruktivna radnja ili odluka koja bitno mijenja cilj/arhitekturu.

Ako naiđeš na bug: reproduciraj -> pronađi uzrok -> popravi -> testiraj -> nastavi.
Ako je feature nedovršen end-to-end, dovrši ga prije novih nepotrebnih featurea.

## RAZVOJNA SIGURNOST

Eksperimentalne promjene radi na zasebnoj development/feature grani. Ne lomi stabilni Unified EOD / Trend Birth pipeline.

Prije završetka/mergea provjeri:
- postojeći pipeline i UI bez regresija
- postojeći kandidati nisu izgubljeni
- Kell overlay ne mijenja originalni StockScout universe
- podaci i rezultat su reproducibilni
- stvarne StockScout kandidate, ne samo synthetic testove
- BEFORE -> AFTER gdje ima smisla.

## KELL IZVORI — TOKEN-EFFICIENT POLICY

**Default referenca za normalan rad je `docs/OLIVER_KELL_REFERENCE.md`.**

Ne učitavaj cijeli PDF `Oliver Kell - Victory in stock market.pdf` po defaultu i ne sažimaj ga ponovno u svakom chatu.

PDF otvori samo kada je potrebno:
- provjeriti točan Kellov tekst ili chart primjer
- razriješiti nejasnoću ili konflikt u MD sažetku
- obraditi Kellov koncept koji nedostaje u MD-u
- prije uvođenja novog pravila/proxyja ako sažetak nije dovoljan.

Ako se MD i PDF razlikuju, **PDF je kanonski izvor**. Ako provjera PDF-a donese važnu novu informaciju ili ispravak, ažuriraj `docs/OLIVER_KELL_REFERENCE.md` kako se PDF ne bi morao ponovno čitati.

Za konkretan zadatak učitaj samo relevantni odjeljak reference/dokumentacije, ne cijele datoteke bez potrebe.

## KELL IMPLEMENTACIJA

Prvo utvrdi što Kell stvarno opisuje, zatim programsku implementaciju.

Ako Kell ne daje numerički prag:
- napravi razuman i testabilan proxy
- jasno ga označi kao **StockScout proxy**
- ne predstavljaj ga kao originalno Kell pravilo.

Uvijek održavaj odvojene slojeve:
- **SCREEN** = zašto je stock pronađen
- **STAGE** = gdje je stock u Cycle of Price Action
- **SETUP** = konkretan actionable pattern

Ne spajaj ih konceptualno samo zato što isti podaci sudjeluju u scoreu.

## PRIORITET RADA

1. ispravnost podataka
2. Screen precision
3. Kell Stage precision
4. Setup precision
5. explainability
6. scoring/ranking
7. UI/UX
8. dodatni featurei.

Cilj nije više signala nego bolja diskriminacija kvalitetnih kandidata.

Kod značajne promjene provjeri realne kandidate i posebno false-positive / false-negative slučajeve. Ne mijenjaj production prag samo zato što stroži validator nešto označi kao borderline; prvo potvrdi chartovima i source logikom.

## AUTONOMIJA

Ako otkriješ malu grešku ili poboljšanje direktno povezano sa zadatkom, popravi ga bez čekanja nove upute.

Ne zaustavljaj se na "sljedeće možemo..." ako taj korak možeš odmah sigurno izvršiti.

Zaustavi se tek kada je cilj stvarno dovršen, dosegnut smislen milestone, postoji blocker/rizik ili je potrebna korisnikova odluka.

## ZAVRŠNI IZVJEŠTAJ

Kratko izvijesti:

**DONE** — što je stvarno implementirano  
**TESTED** — što je provjereno i rezultat  
**FOUND** — važni nalazi/problemi  
**NEXT** — sljedeći logičan korak

Ne predstavljaj nedovršeno kao završeno.
