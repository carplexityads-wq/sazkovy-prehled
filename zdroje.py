# -*- coding: utf-8 -*-
"""
SÁZKOVÝ PŘEHLED – stahování dat pro mobilní aplikaci (spouští GitHub každý den).
 – statistiky za posledních 20 zápasů + nadcházející zápasy.

  Fotbal (8 lig)  -> rohy týmu        zdroj: football-data.co.uk
  NHL             -> góly týmu        zdroj: api-web.nhle.com (oficiální NHL)
  NBA             -> body týmu        zdroj: cdn.nba.com (oficiální NBA)

Vše zdarma, bez registrace a bez klíčů. Stačí Python 3, nic dalšího se neinstaluje.
Spuštění: dvojklik na SPUSTIT.command (Mac), nebo:  python3 prehled.py
Výsledek: prehled.html – otevře se sám v prohlížeči.
"""

import csv, datetime as dt, io, json, os, ssl, subprocess, sys, traceback, urllib.request, webbrowser
from collections import defaultdict

N = 20            # posledních N zápasů
DNI = 7           # nadcházející zápasy na tolik dní dopředu
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "*/*", "Referer": "https://www.nba.com/"}
DNES = dt.date.today()


# ---------------------------------------------------------------- stahování
def stahni(url):
    """Vrátí text, nebo None (404). Když Python nemá certifikáty, použije curl."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode("utf-8-sig", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except (ssl.SSLError, urllib.error.URLError):
        args = ["curl", "-sSfL", "--max-time", "40"]
        for k, v in UA.items():
            args += ["-H", f"{k}: {v}"]
        p = subprocess.run(args + [url], capture_output=True)
        if p.returncode != 0:
            if b"404" in p.stderr:
                return None
            raise RuntimeError(f"Nepodařilo se stáhnout {url}: {p.stderr.decode(errors='replace')[:200]}")
        return p.stdout.decode("utf-8-sig", errors="replace")


def stahni_json(url):
    t = stahni(url)
    return json.loads(t) if t else None


# ---------------------------------------------------------------- společné
def souhrn(zapasy):
    """zapasy: list (datum, vlastní, soupeř, doma:bool). Vrátí řádek tabulky."""
    z = sorted(zapasy, key=lambda x: x[0], reverse=True)[:N]
    h = [x for x in z if x[3]]
    a = [x for x in z if not x[3]]
    s = lambda arr, i: sum(x[i] for x in arr)
    return [len(z), s(z, 1), s(z, 2), len(h), s(h, 1), s(h, 2), len(a), s(a, 1), s(a, 2)]


def sezona_start(mesic_zacatku=7):
    return DNES.year if DNES.month >= mesic_zacatku else DNES.year - 1


# ---------------------------------------------------------------- FOTBAL
LIGY = {"E0": "Anglie", "I1": "Itálie", "D1": "Německo", "SP1": "Španělsko",
        "F1": "Francie", "N1": "Nizozemsko", "B1": "Belgie", "P1": "Portugalsko"}


def fotbal():
    def rows(t):
        return [r for r in csv.DictReader(io.StringIO(t or "")) if r.get("HomeTeam")]

    def datum(s):
        for f in ("%d/%m/%Y", "%d/%m/%y"):
            try:
                return dt.datetime.strptime(s.strip(), f).date()
            except Exception:
                pass

    y = sezona_start()
    akt, pred = f"{y % 100:02d}{(y + 1) % 100:02d}", f"{(y - 1) % 100:02d}{y % 100:02d}"
    ligy = {}
    for kod, nazev in LIGY.items():
        hist, aktualni = defaultdict(list), set()
        for sez in (akt, pred):
            for r in rows(stahni(f"https://www.football-data.co.uk/mmz4281/{sez}/{kod}.csv")):
                if not r.get("HC") or not r.get("AC"):
                    continue
                d, hc, ac = datum(r["Date"]), int(float(r["HC"])), int(float(r["AC"]))
                ht, at = r["HomeTeam"].strip(), r["AwayTeam"].strip()
                if sez == akt:
                    aktualni |= {ht, at}
                hist[ht].append((d, hc, ac, True))
                hist[at].append((d, ac, hc, False))
        ligy[kod] = {"nazev": nazev, "tymy": [[t] + souhrn(hist[t]) for t in sorted(aktualni)]}
        print(f"   ✓ {nazev}: {len(aktualni)} týmů")

    zapasy = []
    for r in rows(stahni("https://www.football-data.co.uk/fixtures.csv")):
        d = datum(r.get("Date", ""))
        if r.get("Div") in ligy and d and DNES <= d <= DNES + dt.timedelta(days=DNI):
            zapasy.append([d.isoformat(), r.get("Time", ""), r["Div"], r["HomeTeam"].strip(), r["AwayTeam"].strip()])
    zapasy.sort()
    return {"nazev": "Fotbal", "stat": "rohy", "ligy": ligy, "zapasy": zapasy}


# ---------------------------------------------------------------- NHL
def nhl():
    st = stahni_json("https://api-web.nhle.com/v1/standings/now")
    tymy = {t["teamAbbrev"]["default"]: t["teamName"]["default"] for t in st["standings"]}
    y = sezona_start(9)
    sezony = [f"{y}{y + 1}", f"{y - 1}{y}"]
    hist = defaultdict(list)
    videno = set()
    for abbr in tymy:
        for sez in sezony:
            data = stahni_json(f"https://api-web.nhle.com/v1/club-schedule-season/{abbr}/{sez}") or {}
            for g in data.get("games", []):
                if g.get("gameType") != 2 or g.get("gameState") not in ("OFF", "FINAL"):
                    continue
                if g["id"] in videno:
                    continue
                videno.add(g["id"])
                d = dt.date.fromisoformat(g["gameDate"])
                h, a = g["homeTeam"], g["awayTeam"]
                if "score" not in h or "score" not in a:
                    continue
                hist[h["abbrev"]].append((d, h["score"], a["score"], True))
                hist[a["abbrev"]].append((d, a["score"], h["score"], False))
    ligy = {"NHL": {"nazev": "NHL", "tymy": [[tymy[t]] + souhrn(hist[t]) for t in sorted(tymy, key=tymy.get)]}}
    print(f"   ✓ NHL: {len(tymy)} týmů")

    zapasy = []
    sch = stahni_json("https://api-web.nhle.com/v1/schedule/now") or {}
    for den in sch.get("gameWeek", []):
        for g in den.get("games", []):
            if g.get("gameType") != 2:
                continue
            ha, aa = g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"]
            if ha in tymy and aa in tymy:
                cas = cas_praha(g.get("startTimeUTC"))
                zapasy.append([den["date"], cas, "NHL", tymy[ha], tymy[aa]])
    return {"nazev": "NHL", "stat": "góly", "ligy": ligy, "zapasy": zapasy}


# ---------------------------------------------------------------- NBA
def nba():
    data = stahni_json("https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json")
    hist, jmena, zapasy = defaultdict(list), {}, []
    for den in data["leagueSchedule"]["gameDates"]:
        for g in den["games"]:
            gid = str(g.get("gameId", ""))
            if not gid.startswith("002"):          # 002 = základní část
                continue
            h, a = g["homeTeam"], g["awayTeam"]
            if not h.get("teamName") or not a.get("teamName"):
                continue
            hn, an = f'{h["teamCity"]} {h["teamName"]}', f'{a["teamCity"]} {a["teamName"]}'
            jmena[hn] = jmena[an] = True
            utc = g.get("gameDateTimeUTC") or g.get("gameDateUTC")
            d = dt.datetime.fromisoformat(utc.replace("Z", "+00:00")).date()
            if g.get("gameStatus") == 3:
                hist[hn].append((d, h["score"], a["score"], True))
                hist[an].append((d, a["score"], h["score"], False))
            elif g.get("gameStatus") == 1 and DNES <= d <= DNES + dt.timedelta(days=DNI):
                zapasy.append([d.isoformat(), cas_praha(utc), "NBA", hn, an])
    zapasy.sort()
    ligy = {"NBA": {"nazev": "NBA", "tymy": [[t] + souhrn(hist[t]) for t in sorted(jmena)]}}
    print(f"   ✓ NBA: {len(jmena)} týmů")
    return {"nazev": "NBA", "stat": "body", "ligy": ligy, "zapasy": zapasy}


def cas_praha(utc):
    """UTC čas -> pražský čas HH:MM (zimní/letní čas podle data)."""
    if not utc:
        return ""
    t = dt.datetime.fromisoformat(utc.replace("Z", "+00:00"))
    y = t.year
    posl_ned = lambda m: max(dt.date(y, m, d) for d in range(25, 32) if dt.date(y, m, d).weekday() == 6)
    leto = dt.datetime.combine(posl_ned(3), dt.time(1), dt.timezone.utc) <= t < \
        dt.datetime.combine(posl_ned(10), dt.time(1), dt.timezone.utc)
    return (t + dt.timedelta(hours=2 if leto else 1)).strftime("%H:%M")


# ---------------------------------------------------------------- hlavní
def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "data.json")
    stare = {}
    if os.path.exists(out):
        try:
            stare = json.load(open(out, encoding="utf-8")).get("sporty", {})
        except Exception:
            pass
    vysledek, chyby = {}, []
    for klic, fn, popis in (("fotbal", fotbal, "Fotbal – rohy"), ("nhl", nhl, "NHL – góly"), ("nba", nba, "NBA – body")):
        print(f"Stahuji {popis}...")
        try:
            vysledek[klic] = fn()
        except Exception as e:
            traceback.print_exc()
            chyby.append(popis)
            if klic in stare:            # když zdroj selže, nech včerejší data
                vysledek[klic] = stare[klic]
    if not vysledek:
        sys.exit("Nic se nestáhlo.")
    teraz = dt.datetime.now(dt.timezone.utc)
    data = {"vytvoreno": teraz.isoformat(), "N": N, "sporty": vysledek, "chyby": chyby}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print("Hotovo:", out, "chyby:", chyby)


if __name__ == "__main__":
    main()
