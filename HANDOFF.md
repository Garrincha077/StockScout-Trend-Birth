## 2026-10-25 — Outcome coverage audit (topic branch, awaiting CI)

- **Source verified:** GitHub Actions #403 on active `feature/unified-review-grid-lab` completed successfully, and the published V2 report is dated 2026-10-23. All **20 archived EOD sessions** have **100% prices** for evaluated tickers; consensus exchange calendar has **22 sessions** since 2026-09-24, with entire EOD gaps **2026-10-15 and 2026-10-19**. This is a major reason the matured 5D outcomes only cover ~71.55–78.38%; the observed 5D means must not recalibrate Composite.
- **Development:** `feature/tb-forward-coverage-audit-20261025` partitions missing matured outcomes into **missing whole market session**, **ticker price absent in an archived session**, and **unclassified**; all buckets reconcile to `missingMatured`. The report exposes archived/expected market sessions, missing dates, and source-quote coverage. The Statistika tab shows the cause breakdown instead of silently collapsing all missingness.
- **Integrity:** forward calculations now reject any EOD-price shard whose `runId` or evaluated universe count differs from immutable stage history. A full-market-session gap disables calibration eligibility even if an individual stage/horizon has 99% coverage. No scores, rankings, alerts, scanners, or existing stored outcomes are changed.
- **Tests / deployment:** Python and Node regression tests added; **topic branch awaiting PR CI**. Do not call this production READY before merge, successful EOD publication, and live UI check. Old V2 reports remain UI-compatible until the next refresh.
- **Next:** merge only after passing CI; inspect 5D missing-cause counts and ensure 20/60D samples mature. Recover missing entire market sessions only from authentic point-in-time EOD sources, without manufacturing quotes; later test split/delisting quality and independent chronological holdout before altering Composite.

---

## 2026-10-25 — Stage forward V2: actual full-universe EOD close archive

- **Why:** production run #402 completed and published stage-forward V1, but **5D outcome coverage was only 43 / 4,368 matured stage entries (about 0.98%)**. The historical prices inside today's rolling Unified chart bars failed to align for most tickers; those averages are not representative and must not calibrate Composite.
- **V2:** use immutable EOD Review snapshots to extract exactly one `metrics.price` per *evaluated ticker per actual day*, preserving `runId` and session-date identity. New script `scripts/archive_trend_birth_closes.py` backfills only missing historical sessions once from existing `lab/data/history`, then processes the new EOD daily. Compact monthly `lab/data/trend-birth-price-history/YYYY-MM.json` keeps every date permanently, without new APIs/services/scans.
- Compute next-EOD-close entry +5/20/60 fully elapsed **exchange-session** closes from the price archives, not from the rolling charts (those now supply **dates only**). New immutable `lab/data/trend-birth-forward-eod-history/YYYY-MM.json` uses schema V2, so 43 prior V1 chart-only results remain available for audit in legacy `trend-birth-forward-history` but cannot contaminate V2 samples. Report `lab/data/trend-birth-stage-forward.json` now schema V2, UI validator updated.
- New snapshot price-contract unit tests; existing stage-entry, chart calendar, pending/missing, immutable archive tests updated. Workflow: price extraction and stage forward after existing stage archive, both monthly archives and compact report included in existing atomic publication. App stays static on GitHub/Vercel.
- **Guardrails:** `metrics.price` is the recorded EOD source quote, not necessarily dividend/split-adjusted; percentages remain descriptive only. Incomplete source-session snapshots are not filled, and missing EOD dates do not become artificial trading sessions. When stock splits/delistings occur, later add corporate-action checks and delisted-outcome review before statistical weight calibration.
- **Next:** inspect real 5D n/coverage from new GH Actions publication. Hold Composite ETF proxy weights unchanged; after 20D/60D maturity and robust sample, use chronological holdout with controls before recalibration.

---

## 2026-10-25 — EOD chart input format hardening

- Source inspection after run #400 established that Unified charts frequently use `[timestamp,open,high,low,close,volume]` arrays and Unix-second/millisecond timestamps, not only `{time,close}` objects. Original new function handled only dicts, yielding false “no reference chart” in CI. Hotfix `_bars()` now normalizes all original source shapes; consensus calendar fix remains as protection for rotating universe. Added regression test for array, seconds, milliseconds, ISO and future-date rejection.
- Need fresh EOD publication workflow to verify both changes and report.

---

## 2026-10-25 — Ispravak nakon realnog GitHub Actions runa #400

- Prvi produkcijski workflow proveo je sve Python i Node testove, potom je novi stage-forward korak javio da AAPL ne postoji u rotirajućem današnjem kandidatskom skupu. Namjenski ispravak: burzovni kalendar se utvrđuje kvorumom >50% svih dostupnih ažurnih Unified grafova s >=10 EOD podataka. Nema dodatnog izvora, nema ovisnosti o stalnom članstvu jednog tickera. Dodan regresijski test bez AAPL-a.
- Objava podataka u workflowu #400 **nije** uspjela, jer se fail-closed pipeline prekinuo prije publication. Nakon hotfix mergea potrebno provjeriti sljedeći run i prve stvarne 5D ishode.

---

## 2026-10-25 — Stvarni ishodi ulaska u Trend Birth faze (5/20/60 EOD)

- Implementacija: `scripts/trend_birth_stage_forward.py`, `tests/test_trend_birth_stage_forward.py`, kompaktne mjesečne arhive `lab/data/trend-birth-forward-history/YYYY-MM.json` te sažetak `lab/data/trend-birth-stage-forward.json`. Jedini ulaz su **već arhivirane** point-in-time ticker faze i `trendBirthCandidateIndex.chartBars` iz postojećeg `latest.json`, bez novih skenova, servisa ili rasporeda.
- Event definicija: isti ticker mora biti valjano evaluiran u dvije uzastopne zabilježene EOD sesije te promijeniti fazu 0–4. Prvi zapis tickera nikad nije automatski ulazak. Jedan event po tickeru/prijelazu; isti ticker može imati više vremenski razdvojenih događaja, koji nisu statistički neovisni.
- Cijene: signal poznat na EOD zatvaranju; **ulaz na idućem sljedećem zabilježenom burzovnom zatvaranju (kalendar iz većine aktualnih Unified grafova)**, potom izlaz za 5, 20 ili 60 cijelih burzovnih sesija. Koristi close-to-close promjenu bez dividendi, slippagea i troškova; rezultat je promatranje, ne izvršen nalog. Nedospjeli eventi ostaju pending; dospjeli bez oba closea broje se u missing, nisu nule. Kalendar je konsenzus datuma preko većine svježih Unified grafova, nema fiksnog tickera koji može nestati iz skupa. Calendar/price freshness fail-closed.
- Svaki dovršen outcome ostaje u malom mjesečnom shardu i kad 260D chart prozor kasnije istekne. Ranije arhivirane faze se ne prepisuju; konflikt događaja/runId za isti dan izaziva fail. Sažetak: za svaku fazu × horizont broj, prosjek, medijan, win-rate, P10/P90, očekivana/dobivena pokrivenost, pending i missing. Prikaz u `lab/statistics.html` zasebno od **ETF proxy Composite**.
- CI workflow: postojeći dnevni job izvršava skriptu nakon arhiviranja faza, čuva i objavljuje mjesečne sharde + sićušan JSON; bez nove Action minute iz zasebnog joba i bez novih Vercel funkcija. Testovi: čista Python sintaksa+core, Node sintaksa, CI unittests.
- **Važna ograničenja:** nedostupne/delistane dionice mogu imati missing outcome (coverage guard); cijene su iz Unified charts i mogu imati split-ali nisu nužno dividend-adjusted; višestruki prijelazi istog tickera i preklapanje 5/20/60 ishoda → nisu nezavisne oklade. `eligibleForCalibration` tek ako pojedina kombinacija faza/horizont ima >=250 dospjelih opažanja, >=20 različitih signalnih dana i >=99% pokrivenosti, ali **ni tada nije automatska promjena Composite težina** bez neovisnog holdouta.
- **Dalje:** provjeriti da CI/GitHub publication i Vercel `statistics.html` u produkciji daju report nakon sljedećeg EOD; dodati benchmark-relative SPY (ako stabilan izvor), survivorship/delisting review, klasterirane intervale pouzdanosti i odvojeni kalibracijski vs budući holdout na većem uzorku.

---

## 2026-10-24 — Walk-forward Composite Score / 14 ETF proxy (eksperimentalno)

- Novi `scripts/backtest_market_internals.py`, `tests/test_trend_birth_composite.py`, te `lab/data/trend-birth-composite-backtest.json`. Pinani izvor je `manisahni/marketdata` commit `65a079329e379e104495f459e12e76a8f995585a` (dividend-adjusted closes od 2004., 14 equity ETF-ova, 9 sektorskih + QQQ/IWM/EFA/EEM/VNQ); bez pohrane velike CSV kopije. Iz izvora se uklanjaju iskljucivo redci bez svih equity cijena (primjer 2026-05-25 i prazni kraj 2026-08-11), a broj takvih redaka cuva se u JSON-u.
- Backtest: walk-forward godisnji, H20 SPY total-return proxy, sljedeci adjusted CLOSE kao ulaz, 10-session stride, 11 predeklariranih modelskih profila, 2008–2026 OOS, obavezni kriza/rast/režim VIX izvjestaji; **nije replay stvarnih povijesnih StockScout setupa**.
- Sest komponenti s historijskim percentilima na vlastitom izvoru; aktualni Composite iz stvarne EOD arhive 2026-09-24 nadalje. Profil ETF proxy prenesen je indikativno, bez dokazane stock-level prediktivnosti.
- Tab `lab/statistics.html` prikazuje score 0–100, sve periode pozitivne/negativne validacije i metodoloske napomene. GitHub workflow lokalno osvjezava aktualni score bez dodatnog network backtesta ili crona.
- Inkrementalni EOD graf `lab/data/trend-birth-market-internals.json` ostaje samo stvarni feed (D/W/M, 1M/3M/1Y/5Y/All), nikakve sinteticke sesije.
- **Sljedece:** kvaliteta cijena/OHLC i dinamicni universe/delistings, neovisni kalibracijski i finalni holdout, provjera metodoloskog rizika te nakon 120+ stvarnih EOD sesija validirati score na punom StockScout univerzumu. Negativni rezimi ukljuceni su u izvjestaj.

---

# HANDOFF — StockScout Trend Birth Review Lab

> **Ažurirano / provjereno:** 24. 10. 2026. (Europe/Zagreb). Ovo je **trenutačni operativni status**, a `docs/PROJECT_LOG.md` je kronološka evidencija promjena. Statuse u nastavku ponovno provjeriti pri idućem radu.

## PRODUKCIJA VERIFIED — Market Internals / Statistika (24. 10. 2026., Europe/Zagreb)

- **PR #53:** https://github.com/Garrincha077/StockScout-Trend-Birth/pull/53 — uspješno spojen squash commmit `1eb8ebe55435d33241cee5914968a73e07bc7905` u aktivnu granu `feature/unified-review-grid-lab`.
- **GitHub CI:** https://github.com/Garrincha077/StockScout-Trend-Birth/actions/runs/40127378812 — **success** (Node i Python testovi uključuju novo računanje, stvarnu arhivu i validaciju cijele publikacije).
- **Vercel production:** deployment `dpl_YYrCvvQChjC8DkENgRGbNsngGo9m` — **READY**; browser uživo učitao https://stockscout-trend-birth-review-lab.vercel.app/statistics i uspješno prikazao graf te 5×5 matricu. Testirani D→M i Acceleration u previewu, browser pristup produkcijskoj strani i podaci provjereni.
- **Source-of-truth podaci:** 20 stvarnih EOD točaka 24.9.–23.10.2026., nema budućeg truncation; posljednje očitanje 23.10. s 163/2614 3+/4 = 6,2357%; pressure 8,3206, vel 5 EOD ~+0,0507 pp/EOD, acceleration ~+0,3426 pp/EOD; flow +61/−38, net +23; matched 2602; percentil 36,84% od 19 prethodnih dana. Kompaktni JSON ~11 KB.
- **Noćni pipeline:** ažurira isti sažetak kroz postojeći EOD workflow i trajne mjesečne arhive; idući **novi EOD refresh nije još viđen uživo**. Prvi sljedeći EOD provjeriti: sessionDate/runId `trend-birth-market-internals.json` = `trend-birth-intelligence.json` = `latest.json`, povijest raste na 21+ (ne resetira se), Telegram nema regresiju.
- **Izvor metodologije / roadmape:** `docs/MARKET_INTERNALS_ROADMAP.md`. Faza 2: preživljavanje kohorti (stvarna ispadanja vs cenzurirani). Faza 3: forward returns i placebo/kontrolni testovi; nema novih trading signala bez tih provjera.

## NOVO: Market Internals — zaseban tab Statistika (rad 24. 10. 2026.)

**Status u ovom prijedlogu:** implementacija i testovi pripremljeni na topic grani `feature/tb-market-internals-20261024`; **produkciju ne proglašavati READY dok PR CI i stvarni Vercel deploy ne prođu**. Polazni commit aktivne grane nakon EOD autopublikacije bio je `3db166a1301d7ba6186f71874cc54769bfe2d825` (GitHub provjeren 24. 10. 2026.).

- Odvojeni `lab/statistics.html`, `lab/trend-birth-stats.js`, `lab/trend-birth-stats.css` i vidljivi tab na postojećem `lab/index.html`. Postojeće kartice kandidata, graf 0/4–4/4 i Telegram format nisu dirani.
- Mali `lab/data/trend-birth-market-internals.json` inicijalno iz **20 stvarnih EOD** točaka 24.9.–23.10.2026., veličine približno **11 KB**. Zadnja sjednica **23.10.2026.**: 2.614 evaluiranih, 3+/4=163 (6,2357%), setup pressure=8,3206/100; zadnji EOD 61 ulaz u 3+/4, 38 izlaza, neto +23 na 2.602 zajednička evaluirana tickera; pokrivenost 99,0861%. Sve vrijednosti dobivene iz kumulativnih mjesečnih arhiva, ne iz procjena.
- `scripts/trend_birth_intelligence.py` sada generira market internals u istom postojećem nightly EOD procesu; dodatni CLI arg `--internals` (opcionalan radi kompatibilnosti), workflow sprema/publikira novi mali JSON istom atomskom logikom.
- D/W/M i rasponi 1M/3M/1Y/5Y/All, zoom 25/50/75/100; povijesni percentil *samo naspram ranijih istovrsnih dnevnih očitanja*, velocity i acceleration odabrani prozor 3/5/10/20 EOD; 5×5 parna matrica prijelaza, net flow i zaštita pokrivenosti.
- **Metodologija / faze 2 i 3:** `docs/MARKET_INTERNALS_ROADMAP.md`. Povijest mora ostati trajna, append-only, nikada samo zadnjih 20. Jedinice, točne definicije, ograničenja kratke povijesti i budući cohort survival te forward testovi su ondje.
- **Testovi:** `tests/test_trend_birth_market_internals.py` i `tests/trend-birth-market-internals.test.cjs`; CI puni unittest discover i node --test. Prije remote commita odrađena Python sintaksa/sintetički test i JS provjera izvornog stvarnog 20-EOD sažetka; GitHub CI i produkcijski UI trebaju zasebnu provjeru.
- **Sljedeće:** dovršiti topic PR, pratiti puni CI, spojiti u `feature/unified-review-grid-lab` samo ako je zelen, provjeriti Vercel stranicu `/statistics.html` i sljedeći EOD refresh bez novih jobova; zatim faza 2 cohort survival i provjera prediktivnosti tek nakon više povijesti.

---

## Trenutačni dodatak — EOD Telegram grupiranje i trajnost setupa (24. 10. 2026.)

**Produkcijski verificirano 24. 10. 2026. (Europe/Zagreb):** PR [#52](https://github.com/Garrincha077/StockScout-Trend-Birth/pull/52) merged u aktivnu granu kao `e1c83658d62a0bc78b7c71f3fe65ff2c3bd29d8f`. GitHub CI run `40123181558` prošao je svih 8 JS i Python provjera te puni read-only snapshot/build/objavu (**success**). Vercel produkcija `dpl_3pgnTFURvWN29TVpiSyVwA9hoHSo` je **READY**. Stvarna stranica prikazuje stabilnost 69/21, ispadanja 38/39, nazivnike 2494/3576 i 1177/2069 te osobne nizove (npr. TRGP 3+/4=12 EOD, 4/4=1 EOD). Telegram format vrijedi **za idući novi EOD generirani payload**, dok arhivirani 23.10. JSON još ima 65 starih poruka; zakazana dostava novog formata u Telegram još nije potvrđena.

- `scripts/trend_birth_intelligence.py`: iz postojećih kumulativnih mjeseci računa `stability` za 3+/4 i 4/4: sadašnji broj; niz najmanje 3 i 5 uzastopnih *zabilježenih EOD* sesija; jednodnevni niz; ispadanja na zadnjem paru; povijesna stopa ostanka sljedećeg EOD-a uz nazivnik samo kada je ticker evaluiran oba dana. Izostanak/nedostupnost prekida niz. Osobni `qualityStreak` i `fourStreak` dodani su samo u deset `topOpportunities` zapisa, ne za svih 2.614 u malom sažetku.
- `scripts/build_trend_birth_alerts.py`: ako postoji važeći EOD intelligence i prethodni radar, svi dotadašnji pojedinačni `trigger` i grupirani `ready`/`invalidated` za istu sesiju postaju **jedna `intelligence-eod` poruka** s imenima i ukupnim brojevima, konzervativno skraćenim popisima i istim dashboard linkom. Stare vrste poruka ostaju kao kompatibilan fallback samo bez intelligence podataka; zasebni hitni/hourly kanali, `v2.weekly` i `v2.kell-daily` nisu izmijenjeni. Ne treba novi Telegram bot ni Unified receiver izmjena jer #112 već prihvaća `intelligence-eod`.
- `lab`: odvojeni blok trajnosti pod Today (3+/4 i 4/4 ≥3 EOD, zadnji padovi, uvjetne stope ostanka) i točan trenutačni niz za top tickere/otvorenu putanju. Ažuriran je samo mali `lab/data/trend-birth-intelligence.json` prema stvarnih 20 mjesečnih točaka kako bi prikaz radio odmah. D/W/M, 1M/3M/1Y/5Y/All, 25/50/75/100 zoom, arhive i stage 0–4 ostaju netaknuti.
- **Izvorni broj 23. 10. na 20 EOD sesija:** 3+/4 =163 ukupno, ≥3 EOD=69, ≥5 EOD=28, ostanak=2.494/3.576=69,7%; 4/4=105 ukupno, ≥3 EOD=21, ≥5 EOD=3, ostanak=1.177/2.069=56,9%. Povijesni postotak nije probabilistička prognoza prinosa. Konačnu verziju i testove provjeriti u PR-u.

## 0. StockScout Intelligence v1 — najnoviji razvoj (24. 10. 2026.)

Implementacija u ovoj radnoj promjeni cilja sljedeće, nadogradnjom postojećeg skenera bez promjene njegovih pravila:

1. **Puna povijest po tickeru i razini 0/4–4/4**: `scripts/trend_birth_intelligence.py` izvlači točne stupnjeve iz `trendBirthCandidateIndex` za sav `unified-plus-tracked-watchlist` univerzum. Sprema dnevne zapise u kumulativne, kalendarski mjesečne `lab/data/trend-birth-ticker-history/YYYY-MM.json` datoteke. Svaki zapis nosi `sessionDate`, `runId`, `stages`, `unavailable`, potpune brojeve i bitmasku deset provjerenih checklist kriterija. Novi datum se pridodaje, stariji mjesečni zapisi se **ne režu prema 20 sesija**. Stariji datumi mogu se učitati samo ako stvarni arhiv sadrži potpun indeks i validan radar; nema interpolacije.
2. **Dnevne prilike**: kompaktni `lab/data/trend-birth-intelligence.json` s brojevima novih 4/4, prelazaka u 3/4, poboljšanja, nazadovanja i najviše deset transparentno prikazanih kandidata. Prijelazi koriste **presjek dvaju evaluiranih univerzuma**, bez lažnih promocija novoobuhvaćenih ili ranije nedostupnih tickera. Nema novog skenera ni neprozirne dodatne ocjene.
3. **UI**: Today's Opportunities se učitava prije višemegabajtnog Review/Kell snimka i naknadno validira prema izvornom datumu, `runId` i stage brojevima. Klik na dnevni/tjedni/mjesečni složeni stupac otvara **točan popis tickera** za odabranu razinu, uz provjeru da zbroj ticker-dana odgovara stupcu. Iz popisa i Today kartica može se otvoriti povijesna putanja tickera; mjesečne datoteke se učitavaju na zahtjev. W/M ostaju ponderirani dnevnim očitanjima, ne broj jedinstvenih dionica.
4. **Automatika i troškovi**: nadograđuje se *postojeći* `.github/workflows/unified-review-grid-lab.yml` bez nove Actions satnice, dodatnog servera ili baze. Mjesečne arhive i sažetak kopiraju se kroz postojeći reset/push blok, čuvaju u GitHubu i serviraju postojećim Vercel Raw rewriteom. U privremeni Actions artefakt ne ulazi arhiva tickera. `build_trend_birth_alerts.py` može dodati jednu dnevnu `intelligence-eod` poruku postojećem **no-send payloadu**; vanjski sender je zaseban repozitorij `StockScout-Unified`; njegov kompatibilni PR **#112** dodaje `intelligence-eod` u strogo odobrene vrste za oba načina slanja (`legacy` i `weekly-v2`). Merge **PR #112 prije ovog PR #51** kako objavljeni JSON ne bi bio odbačen. Ovaj repozitorij **ne šalje** Telegram poruke izravno; početni dan bez valjanog prethodnog Kell podskupa ostaje bez stage-change poruke.
5. **Konzistentnost**: Python provjerava svaki datum, točan nazivnik, 0–4 stage, nedostupne tickere i sukob postojećih sesija; JS zatvara historical drill ako popis nije potpun. Testovi u `tests/test_trend_birth_intelligence.py`, `tests/test_intelligence_telegram.py`, `tests/trend-birth-intelligence.test.cjs`.

**Pri sljedećem chatu:** PR #52 i Unified sender #112 jesu merged; provjeriti prvi sljedeći **novi** EOD s trajno pridodanim ticker sessionom, jednim `intelligence-eod` payloadom i stvarnom Telegram dostavom/ledgerom. Potvrditi ponovljivost postojećih D/W/M zbrojeva, svježinu Vercel Raw rewritea i korisnički prikaz na mobitelu. Ne poistovjećivati programsku kompatibilnost s provjerenom dostavom; ne slati ručno bez potrebe. Raniji status PR #48/#50 niže je povijesni kontekst.

### Produkcijska provjera nakon implementacije (24. 10. 2026., Europe/Zagreb)

- **Merged:** Review Lab PR #51 → `3bcfc2bb7822009b2f238ed8d445d5095bbbc3f5`; Unified Telegram PR #112 → `c3bfbe93810cb5295c56b462d7b0a0350dce3b70`. Nijedan zamrznuti LEGACY skener, ranking niti provider prag nisu mijenjani.
- **Produkcijska objava:** Vercel deployment `dpl_5cv2GGU3faH2s2i5MmtiGae5PRkn` status **READY** i `https://stockscout-trend-birth-review-lab.vercel.app/` HTML status HTTP 200, s novim Today panelom. GitHub EOD run `40119600553` završio je obvezni `build` job **success** i atomskom objavom proizveo commit `2261cdf6885a958e129ffef782e25bff3c579f5f`; pomoćni `historical_calibration` job provjeriti posebno ako je još u tijeku.
- **Povijest stvarno objavljena:** 20 sesija 24. 9. – 23. 10. 2026. u `lab/data/trend-birth-ticker-history/2026-09.json` (5 sesija) i `2026-10.json` (15 sesija). Za svaki dan svih 5 stage brojeva **točno je usklađeno** s `lab/data/trend-birth-quality-history.json`; testiranim D/W/M segmentima to znači **135 uspješnih provjera** (D=100, W=25, M=10).
- **Posljednji EOD 23.10.:** 2.614 evaluiranih, 1 nedostupan; 0/4=2.222, 1/4=182, 2/4=47, 3/4=58, 4/4=105; 3/4+4/4=6,24% / približno P37 na samo 20 sesija. Među 2.602 usporediva tickera: 144 napredovala, 93 nazadovala; 60 novih 4/4 i 16 prelazaka u 3/4. To je **promjena klasifikacije**, ne signal da treba odmah trgovati.
- **Browser proof:** produkcijska stranica prikazuje Today sa stvarnim brojevima, povijesni D i W složeni graf, klik na 23.10. prikazuje točno **105** tickera za 4/4, klik na tjedan 19.–25.10. prikazuje **218 jedinstvenih tickera = 417 ticker-dana** u 4/4. AZTA putanja pokazala je 20 zabilježenih stupnjeva; produkcijski `/data/trend-birth-intelligence.json` vraća HTTP 200.
- **Telegram:** `lab/data/trend-birth-alerts.json` sada sadržava `intelligence-eod` s validiranim podacima i linkom; Unified sender podržava novi tip. **Stvarna isporuka u Telegram nije još potvrđena**; prvi sljedeći zakazani prolaz treba provjeriti u sender ledgers/logovima. Ne pokretati ručno `--send` bez potrebe.
- **Rizik izbjegnut nakon PR #52:** izvještaj 23.10. ostaje nepovratno izvoran sa 65 poruka (62 individualna `trigger` zapisa), ali novi EOD generator uz važeći intelligence automatski spaja te vrste u jedan `intelligence-eod`. Prva stvarna Telegram dostava novog formata i idempotentni sender ledger još nisu potvrđeni; proveriti nakon idućeg EOD-a. Hourly hitne i v2 weekly/kell poruke ostaju odvojene.
- **Idući koraci:** provjeriti prvi novi EOD dan (bez prepisivanja starih mjeseci), stvarnu Telegram dostavu, mobilni UI s arhivom kroz godinu i vremensku/cjenovnu cijenu Vercel/GitHub clone; tek nakon mjerenja odlučivati o daljnjoj optimizaciji velikih raw arhiva.

## 1. Što pročitati prije nastavka

1. `AGENTS.md` — obvezna pravila i ograničenja projekta.
2. Ovaj `HANDOFF.md` — trenutačno stanje, prioriteti i otvorena pitanja.
3. `docs/PROJECT_LOG.md` — povijest izmjena, testova i metodologije.
4. Relevantan izvorni kod i `README.md`, `docs/ROADMAP.md`, `docs/STAGE1_ACCUMULATION_MODEL.md`, `docs/ARCHITECTURE.md` kada započinje veći rad.

**Pravilo za svaki sljedeći AI chat / Codex agent:** najprije pročitati navedene datoteke, potvrditi aktualni GitHub/Vercel status i posljednji EOD datum. Ne pretpostavljati da je zadnji zapisani status još aktualan.

## 2. Repozitorij, objava i integracije

- Repozitorij: https://github.com/Garrincha077/StockScout-Trend-Birth
- **Aktivna produkcijska grana:** `feature/unified-review-grid-lab` (ne `main`).
- Dashboard: https://stockscout-trend-birth-review-lab.vercel.app/
- Vercel projekt: `stockscout-trend-birth-review-lab`, Root Directory `lab`, Git produkcijska grana kao gore.
- Radarski izvor: potvrđeni `trendBirthRadar` iz dnevnog Unified + praćena watchlista pregleda; nije tržišni indeks svih listanih dionica.
- Telegram: postojeća EOD poruka s brojevima 0/4–4/4 i linkom; uže hourly Kell/watchlist poruke ne treba pogrešno predstavljati kao puni dnevni univerzum. Ne uvoditi drugog Telegram pošiljatelja.
- Broker/IBKR i skenerski pragovi nisu izmijenjeni ovim radom.

**Potvrđeno 24. 10. 2026.:**
- PR #48 `https://github.com/Garrincha077/StockScout-Trend-Birth/pull/48` — merged, implementacijski produkcijski commit `777c5a2f503105efce527a1260cfe58ea3d92277`.
- GitHub workflow `40106259332`: `build` i `historical_calibration` = **success**.
- Vercel deployment prethodnog koda `777c5a2` = **READY**. Noviji EOD/data commit `853c193346f7c51bfd99d8fcdedc56a6cf8d7ceb` također je bio **READY** i aktivan na produkcijskoj grani. Pri idućem radu provjeriti stvarnu trenutačnu objavu.
- Potvrđeni kompaktni skup `lab/data/trend-birth-quality-history.json`: **20 stvarnih dnevnih sesija, 24. 9. – 23. 10. 2026.**, ukupno 4.572 bajta. Ne interpolirati datume prije prvog radarskog podatka.
- Zadnje potvrđeno dnevno očitanje 23. 10.: 2.614 ocijenjenih dionica; 3/4 = 58, 4/4 = 105, kombinirano **163 / 2.614 = 6,24 %**, približno **P37** prema 19 prethodnih dnevnih sesija. P je opisni rang uz vrlo mali uzorak.

## 3. Trenutačni povijesni graf: kako mora raditi

- Jedan **100%-složeni stupac** za svako vidljivo razdoblje: 4/4 zeleno dolje, zatim 3/4, 2/4, 1/4, 0/4 crveno gore.
- Odabrane razine ostaju u boji; neodabrane sive, **bez promjene nazivnika**.
- Vertikalni zoom: 0–25%, 0–50%, 0–75%, 0–100%.
- Agregacija: **D / W / M** (dnevno, ISO ponedjeljak–nedjelja, kalendarski mjesec).
- Horizontalni povijesni raspon: **1M / 3M / 1Y / 5Y / All**; `All` doista znači sva arhivirana očitanja, **nema starog ograničenja na 45 stupaca**.
- W/M se računaju **u pregledniku iz svih dnevnih sažetaka**, ponderirano `sum(stageCount) / sum(evaluatedCount)`. W/M brojevi predstavljaju *dionica-dane*, a ne jedinstvene dionice. Pokazati broj pokrivenih sesija i upozorenje za djelomično razdoblje.
- Povijesni percentil koristi ranije usporedive **D s D, W s W, M s M**, svih arhiviranih razdoblja, ne samo trenutačno vidljivih. M percentil zasad nije smislen zbog kratke povijesti.
- Ključni izvori: `lab/app.js`, `lab/index.html`, `lab/styles.css`, `lab/trend-birth-quality.js`. Testovi: `tests/trend-birth-quality.test.cjs`.
- PR #47 uveo je složene stupce/boje/zoom; PR #48 D/W/M i trajni sažetak. Ne vraćati linijski graf.

## 4. Politika trajne povijesti i besplatnih planova

- **Izvor istine za graf:** `lab/data/trend-birth-quality-history.json`. **Čuvati sve stvarne dnevne sažetke trajno**, ne brisati starije od N dana.
- `scripts/trend_birth_quality_history.py` sad spaja novi EOD arhiv s prethodnim provjerenim JSON-om: stariji sažeci ostaju i ako se velike sirove datoteke jednog dana sigurno arhiviraju drugdje. Sukobljen zapis istog dana ili različit univerzum izaziva grešku radi zaštite točnosti.
- Nema dodatnog W/M JSON-a, baze, cron posla ni nove Telegram poruke zbog grafova.
- **Odvojeni problem skladištenja:** pri inventuri 24. 10. `lab/data/history/` imao je 25 velikih JSON-a (~1,89 GiB), a `lab/data/snapshots/` 61 (~4,85 GiB); približno **6,7 GiB nominalne nekomprimirane veličine**, ne isto što i stvarna Git pack veličina. Pojedine datoteke blizu su GitHubova limita od 100 MB.
- **Audit 24. 10.:** `history/` 25 datoteka (~1,89 GiB), `snapshots/` 61 (~4,85 GiB), `kell-history/` 21 (~0,38 GiB), `kell-snapshots/` 53 (~0,82 GiB). Među njima 23/25 Review `history` blobova točno su duplicirani u `snapshots`, a svih 21 Kell `kell-history` blobova u `kell-snapshots`. Git već deduplicira iste SHA blobove; zbroj veličina putanja **nije** stvarna veličina packa.
- **Vercel je već lagan:** `lab/build-vercel.mjs` gradi `dist` bez velikih `lab/data` datoteka; `vercel.json` ih čita putem GitHub Raw rewrites. Nema potrebe za novim Vercel skladištem ni dodatnim buildom.
- **Actions artefakt je bio usko grlo:** uspješni run `40106259332` učitao je `trend-birth-review-grid-lab` artefakt od **2.919.486.005 B** (~2,72 GiB, sa zadanih 7 dana čuvanja). Workflow sada iz tog *privremenog dijagnostičkog artefakta* izuzima stare `history/`, `snapshots/`, `kell-history/`, `kell-snapshots/`, `kell-chart-runs/` i `kell-chart-snapshots/`; **svi izvori ostaju u Git repozitoriju**. Artefakt zadržava isti naziv, trenutačni `latest.json`, `kell-latest.json`, aktualne chart sharde i skripte. Izmjeriti stvarnu manju veličinu nakon sljedećeg uspješnog EOD runa; stari artefakt ne nestaje retroaktivno.
- **Integrity guard:** oba postojeća poziva `trend_birth_quality_history.py` koriste `--latest lab/data/latest.json`. Provjera odbija nedostajući radar, nevaljan zadnji session i nesklad s najnovijim trajno spremljenim očitanjem. Ne dodaje novu akciju, workflow, bazu ni trošak.
- Neki sirovi snapshoti služe point-in-time backtestu/Gold Set istraživanju i nepromjenjivim permalinkovima (`snapshot-loader.js`, `kell_gold_set.py`). **Ništa ne brisati** dok ne postoje provjereni backup, backtest, migracijski plan i korisnikovo odobrenje. Brisanje sa zadnje Git grane samo po sebi ne uklanja stare blobove iz Git povijesti.
- Prioritet je **jednom dnevno** završiti nužni EOD refresh, bez dodatnih napornih buildova i bez plaćenog Vercela.

## 5. Preporučeni sljedeći koraci (redoslijedom)

1. **P0 — Provjera javnog UI-ja na Androidu:** D/W/M, 1M/3M/1Y/5Y/All, svih pet boja i četiri zooma, odabir stupca, prikaz postotaka/percentila. GitHub CI i Vercel `READY` potvrđeni su, ali ručno vizualno QA na fizičkom mobitelu još nije dokumentirano.
2. **P0 — Potvrditi sljedeći stvarni EOD:** provjeriti da `trend-birth-quality-history.json` ima **21. i naredne stvarne sesije** i da starih 20 ostaje. Ako nema novog tržišnog dana, ne stvarati sintetsko očitanje.
3. **P1 — Provjeriti idući stvarni artefakt:** usporediti veličinu nakon šest izuzeća s ranijih 2.919.486.005 B. Potvrditi da `trend-birth-quality-history.json` i današnji `latest.json` imaju istu zadnju sesiju; nastaviti nadzor bez dodatnog joba. Ako integrity guard signalizira nesklad, istražiti podatke, **ne** prepisivati staru povijest.
4. **P1 — Arhivski plan bez brisanja:** audit potrošača i duplikata napravljen; idući korak je izmjeriti stvarni Git pack/repository rast, testirati point-in-time backtest nakon *probne* restauracije u izolaciji i pripremiti eksterni povratni backup prije eventualnog korisničkog odobrenja.
5. **P2 — Povijesna proširenja:** stariji pre-radar snapshoti postoje od 17. 9., no nemaju potvrđeni 0/4–4/4 `trendBirthRadar`; ne predstavljati ih kao verificiranu povijest niti backfillati bez dokazivo iste metodologije i point-in-time ulaza. W/M percentili jačat će kako se gomilaju mjeseci/tjedni.
6. **P2 — Dugoročna UI učinkovitost:** kada sažetak dosegne višegodišnju povijest, provjeriti mobilnu izvedbu `All` prikaza s tisućama dnevnih stupaca; optimizirati prikaz bez gubitka spremljenih podataka.

## 6. Što se radi pri svakom budućem zadatku

- **Prije rada:** pregledati `AGENTS.md`, ovaj dokument i relevantne zadnje stavke `docs/PROJECT_LOG.md`; iz GitHuba/Vercela pročitati aktualni commit, build/objavu, broj i datum sažetaka.
- **Tijekom rada:** zasebna tema/PR, testovi i metodološke napomene; ne mijenjati LEGACY, skenerski ranking, Telegram sender, broker logiku ili velike arhive usput.
- **Nakon značajne promjene:** *ažurirati ovaj `HANDOFF.md`* (status, link na PR, SHA, testovi, posljednji dataset, otvorene točke) i *dopuniti `docs/PROJECT_LOG.md`* (kronologija, obrazloženje). Ne tvrditi da je deployment `READY` dok ga alat ne potvrdi.
- **Nakon promjene chata:** dovoljno je reći: “Nastavi StockScout Trend Birth iz GitHub repozitorija. Prvo pročitaj AGENTS.md, HANDOFF.md i docs/PROJECT_LOG.md, pa provjeri aktualni GitHub/Vercel status i nastavi idući prioritet.” Datoteke čine trajnu primopredaju; sam razgovor nije izvor istine.

## 7. Evidencija ove primopredaje

- 24. 10. 2026.: potvrđeni `READY` Vercel i uspješni `build` + `historical_calibration` za D/W/M. Ponovno očitano svih 20 stvarnih sažetaka. Dodan operativni `HANDOFF.md`, protokol ažuriranja u `AGENTS.md` i poveznica iz `README.md`.
- 24. 10. 2026.: audit velikih raw arhiva i privremenog Actions artefakta; izostavljeno šest arhivskih direktorija samo iz budućih 7-dnevnih dijagnostičkih artefakata, uz zadržavanje Git podataka. Dodan fail-closed integrity guard za latest EOD na obje postojeće točke izrade povijesti; čeka potvrdu na idućem stvarnom workflow runu.
