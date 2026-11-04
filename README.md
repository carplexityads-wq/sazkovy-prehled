# Sázkový přehled

Mobilní aplikace (PWA): statistiky týmů za posledních 20 zápasů – fotbal (rohy, 8 lig), NHL (góly), NBA (body) – a odhad pro nadcházející zápasy proti linii Tipsportu/Fortuny.

- Data stahuje `zdroje.py` (football-data.co.uk, api-web.nhle.com, cdn.nba.com) – zdarma, bez klíčů.
- GitHub Actions (`.github/workflows/data.yml`) data obnovuje každé ráno a ve čt/pá odpoledne a nasazuje web na GitHub Pages.
- Instalace do telefonu: otevřít odkaz → Sdílet → Přidat na plochu (iPhone) / ⋮ → Přidat na plochu (Android).
