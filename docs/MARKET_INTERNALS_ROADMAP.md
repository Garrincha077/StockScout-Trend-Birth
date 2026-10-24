# Roadmap — Market Internals / tab Statistika

**Vlasnik:** StockScout Trend Birth Review Lab · **Datum:** 24. 10. 2026. (Europe/Zagreb)
**Izvor:** trajne point-in-time EOD arhive *lab/data/trend-birth-ticker-history/YYYY-MM.json*
**Osnovno pravilo:** opisujemo cijeli evaluirani univerzum, ne samo kandidate koji su preživjeli selekciju; LEGACY ranking, Trade Signals, Telegram slanje i postojeći glavni graf ne mijenjaju se.

## Cilj i granice

Samostalan tab **Statistika** (putanja /statistics.html) daje strukturni pogled na tržište kroz 0/4–4/4 stanja. Podaci moraju ostati dostupni za 1M/3M/1Y/5Y/All i D/W/M, bez brisanja starih valjanih očitanja. Nema fiktivne povijesti za prije uvođenja radara (prvi stvarni EOD = 2026-09-24) i nema novih računanja indikatora iz cijena ili dodatnih API poziva.

## Faza 1 — Transparentna statistika i prijelazi (ovaj PR)

- [x] Novi **Statistika** tab s odvojenim HTML/JS/CSS, bez promjene postojećih Review tabova.
- [x] Jedna mala append-only izvedena povijest *lab/data/trend-birth-market-internals.json*, nastaje unutar postojećeg GitHub Action joba.
- [x] Quality breadth 3+/4, udio 4/4, Setup Pressure 0–100; graf stupaca D/W/M i 1M/3M/1Y/5Y/All; zoom 0–25/50/75/100.
- [x] Velocities (linearni nagib za prozor 3/5/10/20 EOD); accelerations (razlika nagiba dvaju nepoklopljenih prozora), s eksplicitnim null kada nedostaje 2×N.
- [x] Quality i 4/4 ulazi/izlazi i neto tok, samo u presjeku evaluiranih tickera između dvije arhivirane EOD sesije.
- [x] Pokrivenost i Jaccard overlap evaluiranog univerzuma; ne tretirati nedostupnog/novog/nestalog kao 0/4.
- [x] Matrica 5×5 EOD prijelaza s rednim postotcima za odabrano razdoblje; broj ticker-prijelaza.
- [x] Percentil **zadnjeg dnevnog** opažanja u odnosu na ranija dnevna opažanja istog pokazatelja uz n; bez budućih podataka.
- [x] Četiri opisna stanja (nagib +/- i akceleracija +/-), bez backtestom nepotvrđenih granica.
- [x] Jedinice, metodološka ograničenja i redoviti testovi; spremnost produkcije ovisi o CI i Vercel provjeri.

### Točne definicije

- Dnevni EOD N_s(t): svi evaluirani tickeri s fazom s∈{0,1,2,3,4}. N(t)=ΣN_s(t). Nedostupan ticker se **ne ubraja** ni u s=0 ni u N.
- **Breadth3+(t)** = 100·(N₃+N₄)/N, **Breadth4(t)** = 100·N₄/N.
- **Pressure(t)** = 100·Σ(s·N_s)/(4·N). Jedinica je indeks 0–100, ne postotak prinosa.
- **Velocity(t,w)** = OLS nagib dnevne serije breadth3+ kroz zadnjih w *zabilježenih EOD* sesija, u **postotnim bodovima po zabilježenom EOD-u**.
- **Acceleration(t,w)** = velocity(t,w) − velocity(t−w,w); razlika nagiba dvaju **nepreklapajućih** EOD prozora; valjana nakon ≥2w sesija. Jedinica je promjena nagiba (pp/EOD), a ne druga derivacija po kalendarskom danu.
- **Inflows(t)** = broj zajedničkih evaluiranih tickera prethodno 0–2, a sada 3–4. **Outflows(t)** = prethodno 3–4, a sada 0–2. Neto = inflows−outflows. Za 4/4 granica je 4 vs 0–3.
- **MatchedQualityDeltaPp** = postotni bodovi promjene kvalitete među **istim evaluiranim tickerima**, odvojeno od promjene ukupnog skupa.
- **Overlap(t)** = 100·|Sₜ ∩ Sₜ₋₁| / |Sₜ ∪ Sₜ₋₁| za skupove evaluiranih tickera. Novo i nestalo su odvojene brojke.
- **Povijesni percentil** = 100·(broj prošlih vrijednosti manjih od zadnje + 0,5×broj jednakih)/broj *prošlih* validnih opažanja, usporedba uvijek **D**; ne uspoređivati D percentil s W/M.
- **W/M agregacija**: zbroj pet brojeva faza i evaluiranih ticker-dana svih sesija razdoblja; breadth/pressure iz tih zbrojeva. Ticker prisutan pet EOD dana ulazi pet puta (ticker-dani), što se jasno označava.
- Matrica za filter razdoblja zbraja sve dnevne uzastopne EOD parove čija **oba** kraja padaju u odabrano razdoblje; svaki prijelaz jednog tickera je opažanje, redni postotci = Nᵢⱼ/ΣⱼNᵢⱼ.

### Povijesne i resursne zaštite

- Trajno pohranjuj sve stvarno zabilježene EOD točke; *ne skraćuj na 20*. Arhiva raste append-only po mjesecima, a kompaktna serija se svaki put reproducibilno generira iz nje.
- Jedan postojeći GitHub Action EOD job i jedno pisanje JSON-a. Bez dodatnog crona, bez Supabase nove tablice, bez novog Vercel Function poziva, bez promjene strategije.
- Vercel dalje poslužuje samo mali statički UI, a kompaktni JSON putem postojećeg /data/* proxyja na GitHub Raw.
- Ne dohvaćati velike ticker-arhive pri otvaranju Statistika taba; one ostaju za drill-down glavnog ekrana, gdje se već selektivno dohvaćaju.
- Podaci nisu trenutni market breadth za sve NYSE/Nasdaq kompanije; obuhvat je unified-plus-tracked-watchlist.
- CI/testovi moraju verificirati: pet faza zbrojem = N, matrica zbrojem = matched, razilaženje scope/runId/datuma = greška, nedostupnost ne postaje 0/4.

## Faza 2 — Praćenje pravih kohorti (sljedeći prioritet)

1. **Age / cohort survival**: od datuma ulaska u 2/4, 3+/4 ili 4/4 do izlaska, uključujući desno cenzurirane slučajeve; Kaplan–Meier ili jednostavne kumulativne stope po 5/10/20/60 EOD, uz denominatore.
2. **Quality persistence stratifikacija**: uvjetni ostanak i povratak 0/4–4/4 na 3, 5, 10, 20 EOD; odvojiti konzistentan uzorak vs ulazak/izlazak iz univerzuma.
3. **Net change vs cohort effect**: koliko promjene kvalitete dolazi iz istih tickera, a koliko iz širenja/sužavanja pokrivenosti. Procjena robusnosti na promjenjivu watchlistu.
4. **Alerts bez buke**: obavijestiti Telegram samo kad validirani interni indikator odstupa po unaprijed određenoj i backtestiranoj razini; treba više EOD uzoraka prije pragova.

## Faza 3 — Validacija tržišnih implikacija (tek s više povijesti)

1. Usporediti breadth/pressure/velocity/acceleration s SPY, RSP, QQQ i eventualno njihovim budućim prinosima uz cijene vremenski poravnate bez look-ahead.
2. Forward 5/20/60/120/252 EOD performanse po **svim** početnim setupima, ne samo winnerima; uključiti negativne i delistane.
3. Kontrole: fiksni vs promjenjivi univerzum, rebalance, sektor/market-cap, random/naive baseline, out-of-sample, kalibracija i ablation.
4. Tek tada uvesti interpretaciju risk-on/risk-off, divergence, z-score ili trigger pragove; ne miješati opis i dokaz prediktivne moći.

## Acceptance / sljedeći operativni potez

- CI: Python testovi stvarnih arhiva i sintetičkih tranzicija; JS testovi normalizacije, percentila, EOD prozora i W/M agregacije.
- Ručno: desktop/mobitel render /statistics.html, 1M/3M/All, D/W/M, zoom 25→100, prebacivanje u Review i natrag.
- Produkcija: provjeriti deploy **READY**, /data/trend-birth-market-internals.json nov i usklađen s /data/latest.json, do idućeg EOD-a pratiti pipeline.
- Nakon što ima ≥60 EOD sesija, ponovno ocijeniti stabilnost percentila, ali ne čekati 60 dana za zapisivanje povijesti.
