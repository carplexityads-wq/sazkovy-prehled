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


def sjednot(nazev, tymy):
    """Rozpis občas píše jméno jinak než výsledky (KV Mechelen x Mechelen)."""
    import difflib
    n = nazev.strip()
    if n in tymy:
        return n
    for t in tymy:
        if t.lower() in n.lower() or n.lower() in t.lower():
            return t
    m = difflib.get_close_matches(n, tymy, n=1, cutoff=0.6)
    return m[0] if m else n


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
            jm = [t[0] for t in ligy[r["Div"]]["tymy"]]
            zapasy.append([d.isoformat(), r.get("Time", ""), r["Div"], sjednot(r["HomeTeam"], jm), sjednot(r["AwayTeam"], jm)])
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
            if g.get("gameType") != 2 or g.get("gameState") not in ("FUT", "PRE"):
                continue
            ha, aa = g["homeTeam"]["abbrev"], g["awayTeam"]["abbrev"]
            if ha in tymy and aa in tymy:
                cas = cas_praha(g.get("startTimeUTC"))
                zapasy.append([den_praha(g.get("startTimeUTC"), den["date"]), cas, "NHL", tymy[ha], tymy[aa]])
    zapasy.sort()
    return {"nazev": "NHL", "stat": "góly", "ligy": ligy, "zapasy": zapasy}


# ---------------------------------------------------------------- NBA
def nba():
    """ESPN veřejné API (cdn.nba.com blokuje servery GitHubu)."""
    base = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{}/schedule"
    y = sezona_start(9) + 1                      # ESPN značí sezónu 2026/27 jako 2027
    hist, jmena, zapasy, videno, budouci = defaultdict(list), set(), [], set(), set()
    for tid in range(1, 31):
        for q in ("", f"?season={y - 1}&seasontype=2"):
            data = stahni_json(base.format(tid) + q) or {}
            for ev in data.get("events", []):
                if (ev.get("seasonType") or {}).get("type") != 2:
                    continue
                comp = ev["competitions"][0]
                cs = {c["homeAway"]: c for c in comp["competitors"]}
                if "home" not in cs or "away" not in cs:
                    continue
                hn, an = cs["home"]["team"]["displayName"], cs["away"]["team"]["displayName"]
                jmena |= {hn, an}
                d = dt.datetime.fromisoformat(ev["date"].replace("Z", "+00:00"))
                if comp["status"]["type"].get("completed"):
                    if ev["id"] in videno:
                        continue
                    videno.add(ev["id"])
                    hs, as_ = float(cs["home"]["score"]["value"]), float(cs["away"]["score"]["value"])
                    hist[hn].append((d.date(), hs, as_, True))
                    hist[an].append((d.date(), as_, hs, False))
                elif ev["id"] not in budouci and DNES <= d.date() <= DNES + dt.timedelta(days=DNI):
                    budouci.add(ev["id"])
                    zapasy.append([den_praha(ev["date"], d.date().isoformat()), cas_praha(ev["date"]), "NBA", hn, an])
    zapasy.sort()
    ligy = {"NBA": {"nazev": "NBA", "tymy": [[t] + [round(x) if isinstance(x, float) else x for x in souhrn(hist[t])] for t in sorted(jmena)]}}
    print(f"   ✓ NBA: {len(jmena)} týmů")
    return {"nazev": "NBA", "stat": "body", "ligy": ligy, "zapasy": zapasy}


def den_praha(utc, zaloha):
    """Datum zápasu podle pražského času (zápas v 1:30 u nás je už další den)."""
    if not utc:
        return zaloha
    t = dt.datetime.fromisoformat(utc.replace("Z", "+00:00"))
    h, m = map(int, cas_praha(utc).split(":"))
    posun = (h * 60 + m - (t.hour * 60 + t.minute)) % (24 * 60)
    return (t + dt.timedelta(minutes=posun)).date().isoformat()


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
