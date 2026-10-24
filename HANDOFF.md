# HANDOFF — StockScout Trend Birth Review Lab

> **Ažurirano / provjereno:** 24. 10. 2026. (Europe/Zagreb). Ovo je **trenutačni operativni status**, a `docs/PROJECT_LOG.md` je kronološka evidencija promjena. Statuse u nastavku ponovno provjeriti pri idućem radu.

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
- Neki sirovi snapshoti služe point-in-time backtestu/Gold Set istraživanju. **Ništa ne brisati** dok se ne napravi inventura potrošača, testovi i backtest, provjerena povratna kopija te korisnik ne odobri opseg. Brisanje sa zadnje Git grane samo po sebi ne uklanja stare blobove iz Git povijesti.
- Prioritet je **jednom dnevno** završiti nužni EOD refresh, bez dodatnih napornih buildova i bez plaćenog Vercela.

## 5. Preporučeni sljedeći koraci (redoslijedom)

1. **P0 — Provjera javnog UI-ja na Androidu:** D/W/M, 1M/3M/1Y/5Y/All, svih pet boja i četiri zooma, odabir stupca, prikaz postotaka/percentila. GitHub CI i Vercel `READY` potvrđeni su, ali ručno vizualno QA na fizičkom mobitelu još nije dokumentirano.
2. **P0 — Potvrditi sljedeći stvarni EOD:** provjeriti da `trend-birth-quality-history.json` ima **21. i naredne stvarne sesije** i da starih 20 ostaje. Ako nema novog tržišnog dana, ne stvarati sintetsko očitanje.
3. **P1 — Audit pohrane:** mapirati što koristi `history/`, `snapshots/` i druge velike arhive; identificirati dupliciranje i što zaista ide u Vercel build/artifact. Napraviti reproduktibilnu analizu/backtest i plan arhiviranja prije bilo kakvog brisanja. Tražiti odobrenje za destruktivni dio.
4. **P2 — Povijesna proširenja:** stariji pre-radar snapshoti postoje od 17. 9., no nemaju potvrđeni 0/4–4/4 `trendBirthRadar`; ne predstavljati ih kao verificiranu povijest niti backfillati bez dokazivo iste metodologije i point-in-time ulaza. W/M percentili jačat će kako se gomilaju mjeseci/tjedni.
5. **P2 — Dugoročna UI učinkovitost:** kada sažetak dosegne višegodišnju povijest, provjeriti mobilnu izvedbu `All` prikaza s tisućama dnevnih stupaca; optimizirati prikaz bez gubitka spremljenih podataka.

## 6. Što se radi pri svakom budućem zadatku

- **Prije rada:** pregledati `AGENTS.md`, ovaj dokument i relevantne zadnje stavke `docs/PROJECT_LOG.md`; iz GitHuba/Vercela pročitati aktualni commit, build/objavu, broj i datum sažetaka.
- **Tijekom rada:** zasebna tema/PR, testovi i metodološke napomene; ne mijenjati LEGACY, skenerski ranking, Telegram sender, broker logiku ili velike arhive usput.
- **Nakon značajne promjene:** *ažurirati ovaj `HANDOFF.md`* (status, link na PR, SHA, testovi, posljednji dataset, otvorene točke) i *dopuniti `docs/PROJECT_LOG.md`* (kronologija, obrazloženje). Ne tvrditi da je deployment `READY` dok ga alat ne potvrdi.
- **Nakon promjene chata:** dovoljno je reći: “Nastavi StockScout Trend Birth iz GitHub repozitorija. Prvo pročitaj AGENTS.md, HANDOFF.md i docs/PROJECT_LOG.md, pa provjeri aktualni GitHub/Vercel status i nastavi idući prioritet.” Datoteke čine trajnu primopredaju; sam razgovor nije izvor istine.

## 7. Evidencija ove primopredaje

- 24. 10. 2026.: potvrđeni `READY` Vercel i uspješni `build` + `historical_calibration` za D/W/M. Ponovno očitano svih 20 stvarnih sažetaka. Dodan operativni `HANDOFF.md`, protokol ažuriranja u `AGENTS.md` i poveznica iz `README.md`.
