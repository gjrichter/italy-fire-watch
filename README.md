# italy-fire-watch

Pipeline giornaliera che scarica gli hotspot satellitari attivi su Italia (SUOMI VIIRS C2, NOAA-20/J1 VIIRS C2, MODIS C6.1 — le stesse fonti usate da EFFIS) dai file pubblici NASA FIRMS, e ne filtra via le sorgenti di calore industriali note (altiforni, raffinerie, centrali, inceneritori) che altrimenti vengono segnalate come incendi.

## Come funziona

1. `scripts/fetch_hotspots.py` — scarica i CSV rolling 7 giorni per l'Europa da FIRMS e accumula i nuovi punti in `hotspot_history.csv`.
2. `scripts/build_mask.py` — unisce `known_sources_seed.geojson` (lista curata a mano) con le celle che risultano "persistenti" nello storico (≥10 giorni distinti su una finestra di 60), producendo `exclusion_mask.geojson`.
3. `scripts/filter_fires.py` — pubblica `italy_fires_current.geojson`, gli hotspot recenti con tutto ciò che cade nel buffer della mask rimosso.

Un [GitHub Action](.github/workflows/update-fires.yml) esegue i tre script ogni giorno e committa gli output aggiornati.

## Consumo dati

`italy_fires_current.geojson` è pensato per essere caricato via CDN (jsDelivr) in una mappa ixMaps o in qualsiasi altro consumer GeoJSON.

## Nota sulle coordinate seed

Le voci in `known_sources_seed.geojson` con `verified:false` sono stime geografiche non ancora confrontate con dati reali; verranno corrette (o sostituite dalla mask automatica) quando emergeranno rilevazioni vicine.
