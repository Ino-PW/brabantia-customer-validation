# Consumer-segmentatie pipeline

Deze pipeline segmenteert consumenten per land met een Gaussian Mixture Model (GMM),
bepaalt hoeveel segmenten (clusters) daarvoor optimaal zijn, en berekent statistieken
en een PCA-reductie over de resulterende segmenten.

De pipeline is opgesplitst in genummerde stappen (`005`, `006`, `010`, `020`, `030`)
die je los kunt draaien, of via twee orchestrator-scripts in de juiste volgorde
achter elkaar: eerst verkennen, dan pas de volledige productie-run.

---

## Inhoudsopgave

1. [Snelstart](#snelstart)
2. [Vereisten](#vereisten)
3. [Bestandsstructuur](#bestandsstructuur)
4. [De twee fases van de workflow](#de-twee-fases-van-de-workflow)
5. [Configuratie (`config.py`)](#configuratie-configpy)
6. [De stappen in detail](#de-stappen-in-detail)
7. [Outputbestanden](#outputbestanden)
8. [Logging](#logging)
9. [Bekende ontwerpkeuzes en beperkingen](#bekende-ontwerpkeuzes-en-beperkingen)
10. [Veelvoorkomende problemen](#veelvoorkomende-problemen)
11. [Pipeline uitbreiden](#pipeline-uitbreiden)

---

## Snelstart

```bash
# Fase 1 — verkennen: hoeveel clusters zijn optimaal per land?
python run_cluster_selection.py

# Bekijk de resultaten:
#   results/cluster_selection.csv
#   results/figures/cluster_selection_{land}.png

# Pas config.py aan met je gekozen aantal clusters per land, bijvoorbeeld:
#   GMM_N_COMPONENTS = {"NL": 5, "BE": 6, "FR": 4, "DE": 6, "GB": 7, "ES": 6}

# Fase 2 — productie: de volledige pipeline draaien met die keuzes
python run_pipeline.py
```

---

## Vereisten

- Python 3.10+ (vanwege `dict[str, int]`-type hints en `X | None`-syntax)
- Packages: `pandas`, `numpy`, `scikit-learn`, `torch`, `tgmm`, `matplotlib`
- Een GPU is niet vereist — als `torch.cuda.is_available()` `False` teruggeeft,
  draait alles gewoon op de CPU (wel trager bij grote datasets)

Installeren:

```bash
pip install pandas scikit-learn torch matplotlib
pip install tgmm  # of installeer vanuit de juiste interne bron
```

---

## Bestandsstructuur

```
pipeline/
├── config.py                                  # Alle gedeelde instellingen (paden, landen, parameters)
├── data_loading.py                            # Gedeelde functies: data inladen/opschonen + features selecteren
├── logging_utils.py                           # Gedeelde logging-config: stdout + logbestand per run
│
├── run_cluster_selection.py                   # Orchestrator FASE 1: draait 005 + 006
├── run_pipeline.py                             # Orchestrator FASE 2: draait 010 + 020 + 030
│
├── 005-cluster-selection-pipeline.py           # Sweept k=2..10 per land, scoort met silhouette/BIC/AIC
├── 006-visualise-cluster-selection-pipeline.py # Plot silhouette-score vs. aantal clusters per land
├── 010-gmm-pipeline.py                         # Productie-fit: GMM per land met gekozen n_components
├── 020-stats-pipeline.py                       # Clusterstatistieken per land (bevat eigen stats-helpers)
├── 030-pca-pipeline.py                         # PCA per land op de gesegmenteerde data
│
├── data/
│   └── amount_of_orders_data.csv               # Ruwe inputdata (zelf aan te leveren)
│
└── results/                                    # Wordt automatisch aangemaakt
    ├── cluster_selection.csv                   # Output van 005
    ├── figures/
    │   └── cluster_selection_{land}.png         # Output van 006, één plot per land
    ├── consumers_{land}.csv                     # Output van 010, één bestand per land
    ├── consumers_met_segmenten_per_land.csv     # Output van 010, alle landen samengevoegd
    ├── stats.csv                                # Output van 020
    ├── consumers_met_pca.csv                    # Output van 030
    ├── PCA.txt                                  # Output van 030, leesbaar tekstrapport
    └── logs/
        └── run_{timestamp}.log                  # Eén logbestand per proces/run, alle stappen samen
```

**Let op de nummering:** de stapnummers geven de logische volgorde weer, niet per se
de importvolgorde in Python (bestandsnamen met een koppelteken en een cijfer
vooraan kun je niet direct `import`eren — de orchestrators laden ze daarom via
`importlib` op basis van bestandspad).

---

## De twee fases van de workflow

### Fase 1 — Verkennen: hoeveel clusters zijn optimaal?

```bash
python run_cluster_selection.py
```

Dit draait:

1. **`005-cluster-selection-pipeline.py`** — laadt de ruwe (opgeschoonde) data,
   en fit per land een GMM voor elk aantal clusters tussen
   `config.CLUSTER_SELECTION_K_MIN` en `config.CLUSTER_SELECTION_K_MAX`
   (standaard 2 t/m 10). Elke fit wordt gescoord met de silhouette-score, en
   met BIC/AIC als `tgmm`'s `GaussianMixture` die methodes aanbiedt.
2. **`006-visualise-cluster-selection-pipeline.py`** — leest die resultaten
   en tekent per land een elleboog-plot (silhouette-score tegen aantal
   clusters).

**Belangrijk:** deze fase draait *voordat* de productie-GMM (stap `010`)
draait — hij hangt niet af van stap `010`'s output. Zo weet je hoeveel
segmenten realistisch zijn per land vóórdat je tijd steekt in de volledige
fit en alles wat daarna komt (statistieken, PCA).

Na afloop:

- Bekijk `results/cluster_selection.csv` en de plots in `results/figures/`.
- Er is geen "juist" antwoord dat het script voor je kiest — de hoogste
  silhouette-score is niet automatisch de beste keuze. Een lagere, minder
  optimale score kan een aantal segmenten opleveren dat beter uit te leggen
  is aan de business. Gebruik de plot en de logging (die het beste
  scorende `k` per land benoemt) als hulpmiddel, niet als eindoordeel.

### Fase 2 — Productie: de volledige pipeline draaien

Pas eerst het `GMM_N_COMPONENTS`-dictionary in `config.py` aan met je gekozen
aantal clusters per land:

```python
GMM_N_COMPONENTS: dict[str, int] = {
    "NL": 5,
    "BE": 6,
    "FR": 4,
    "DE": 6,
    "GB": 7,
    "ES": 6,
}
```

Draai dan:

```bash
python run_pipeline.py
```

Dit draait:

1. **`010-gmm-pipeline.py`** — de definitieve GMM-fit per land, met het
   aantal clusters uit `config.GMM_N_COMPONENTS[land]`. Staat een land niet
   in dat dictionary, dan valt de pipeline terug op
   `config.GMM_N_COMPONENTS_DEFAULT` én geeft een waarschuwing.
2. **`020-stats-pipeline.py`** — berekent clusterstatistieken per land op
   basis van de segmentlabels uit stap `010`.
3. **`030-pca-pipeline.py`** — voert per land een PCA uit op de
   gesegmenteerde data, voor exploratieve analyse/visualisatie.

---

## Configuratie (`config.py`)

Alle instellingen staan op één plek, zodat je ze niet in meerdere scripts
hoeft aan te passen.

| Instelling | Betekenis |
|---|---|
| `LANDEN` | Lijst van landcodes die door elke stap verwerkt worden |
| `ID_COL` | Kolomnaam van de unieke consument-identifier |
| `COUNTRY_COL` | Kolomnaam die het land van een rij aangeeft in de brondata |
| `LAND_COL` | Kolomnaam `"land"` zoals gebruikt in resultaattabellen (`stats.csv`, `cluster_selection.csv`) |
| `EXCLUDE_TERMS` | Substrings (bv. `"segment"`) — kolommen die dit bevatten worden uitgesloten van numerieke modellering |
| `GMM_INPUT_PATH` | Pad naar de ruwe inputdata |
| `GMM_N_COMPONENTS` | **Dictionary** met het aantal clusters per land — hier vul je je keuze uit fase 1 in |
| `GMM_N_COMPONENTS_DEFAULT` | Terugvaloptie als een land niet in het dictionary staat |
| `GMM_ID_COLS`, `GMM_EXTRA_EXCLUDE_COLS` | Kolommen die nooit meegenomen worden als GMM-feature |
| `CLUSTER_SELECTION_K_MIN` / `_K_MAX` | Bereik van te testen aantal clusters in fase 1 |
| `CLUSTER_SELECTION_N_INIT` | Aantal herstarts per fit in fase 1 (lager dan productie, want er worden veel meer fits gedraaid) |
| `CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` | Max. aantal rijen gebruikt voor de silhouette-berekening (silhouette is O(n²), dus dit voorkomt trage runs bij grote datasets) |
| `PCA_N_COMPONENTS` | Aantal PCA-componenten |
| `PCA_TOP_N_FEATURES` | Aantal features dat getoond wordt per component in `PCA.txt` |
| `PCA_VARIANCE_TARGET` | Doel voor cumulatieve verklaarde variantie (standaard 90%) in het rapport |

---

## De stappen in detail

### `data_loading.py` (gedeeld, geen losse stap)

Bevat twee functies die zowel door `005` als `010` gebruikt worden, zodat
de featureset in de verkennende sweep en de productie-fit nooit uit elkaar
kunnen lopen:

- **`load_and_clean(input_path)`** — leest de ruwe CSV in, zet de kolom
  `KOOPKRACHT` om van tekst naar numeriek, en vult ontbrekende waarden op
  met de **kolommediaan** (over alle landen heen, vóór de opsplitsing per
  land — zie [Bekende ontwerpkeuzes](#bekende-ontwerpkeuzes-en-beperkingen)).
- **`prepare_features(df_land)`** — verwijdert ID-, land-, categorische en
  segment-gerelateerde kolommen, zodat alleen echte modelfeatures overblijven.

### `005-cluster-selection-pipeline.py`

- **Input:** ruwe data via `load_and_clean`.
- **Werking:** per land, per `k` in het geconfigureerde bereik, een GMM
  fitten en scoren met silhouette (en BIC/AIC indien beschikbaar).
- **Output:** `results/cluster_selection.csv` met kolommen
  `land`, `n_clusters`, `silhouette_score`, en optioneel `bic`/`aic`.
- **Let op:** dit script fit meerdere modellen per land (standaard 9, voor
  k=2 t/m 10) en kan daardoor merkbaar langer duren dan de productie-fit
  (stap `010`, die maar één `k` fit).

### `006-visualise-cluster-selection-pipeline.py`

- **Input:** `results/cluster_selection.csv`.
- **Output:** `results/figures/cluster_selection_{land}.png` — één
  elleboogplot per land (aantal clusters op de x-as, silhouette-score op
  de y-as).

### `010-gmm-pipeline.py`

- **Input:** ruwe data via `load_and_clean` (zelfde functie als `005`).
- **Werking:** per land een GMM fitten met het aantal clusters uit
  `config.GMM_N_COMPONENTS[land]`. De `StandardScaler` wordt **per land**
  apart gefit — dit is bewust, anders vergelijk je landen onderling in
  plaats van consumenten binnen een land te segmenteren.
- **Output:**
  - `results/consumers_{land}.csv` — per land, met kolommen `segment` en
    `segment_{i}_kans` (kans per cluster) toegevoegd.
  - `results/consumers_met_segmenten_per_land.csv` — alle landen
    samengevoegd, met een extra kolom `segment_globaal`
    (`{land}_{segment}`), omdat segmentnummers alleen uniek zijn *binnen*
    een land.

### `020-stats-pipeline.py`

- **Input:** de per-land bestanden uit stap `010`
  (`results/consumers_{land}.csv`).
- **Werking:** berekent per land clusterstatistieken (grootte per cluster,
  beschrijvende statistieken per feature, silhouette per cluster, en
  overall silhouette/Calinski-Harabasz/Davies-Bouldin) op de numerieke
  kolommen (exclusief kolommen die `EXCLUDE_TERMS` bevatten). Deze helpers
  stonden voorheen in een aparte `utils.py` die niet bij dit pakket zat -
  ze zijn nu direct in dit bestand gedefinieerd, dus `020` heeft geen
  externe dependency meer en draait out of the box.
- **Output:** `results/stats.csv`, met een kolom `land` erbij.

### `030-pca-pipeline.py`

- **Input:** `results/consumers_met_segmenten_per_land.csv` (output van
  stap `010`).
- **Werking:** per land een PCA uitvoeren op de numerieke, niet-uitgesloten
  kolommen (na standaardisatie). Landen met te weinig rijen voor het
  gevraagde aantal componenten worden overgeslagen (met een waarschuwing).
- **Output:**
  - `results/consumers_met_pca.csv` — ID, PCA-scores en de uitgesloten
    (segment-)kolommen.
  - `results/PCA.txt` — leesbaar rapport per land met verklaarde variantie,
    loadings en de top features per component.

---

## Outputbestanden

| Bestand | Gemaakt door | Inhoud |
|---|---|---|
| `results/cluster_selection.csv` | `005` | Silhouette/BIC/AIC per land per geteste `k` |
| `results/figures/cluster_selection_{land}.png` | `006` | Elleboogplot per land |
| `results/consumers_{land}.csv` | `010` | Ruwe data + segmentlabel + segmentkansen, per land |
| `results/consumers_met_segmenten_per_land.csv` | `010` | Alle landen samen + `segment_globaal` |
| `results/stats.csv` | `020` | Clusterstatistieken per land |
| `results/consumers_met_pca.csv` | `030` | ID + PCA-scores + segmentkolommen |
| `results/PCA.txt` | `030` | Leesbaar PCA-rapport per land |
| `results/logs/run_{timestamp}.log` | elke stap | Alle logregels van het proces dat je startte (bv. een volledige `run_pipeline.py`-run), na afloop terug te lezen |

---

## Logging

Elk script gebruikt `logging_utils.get_logger(naam)` voor consistente,
tijdgestempelde logregels. Elke logger schrijft naar **twee** plekken:

1. **stdout** — zoals voorheen, om een run live te kunnen volgen.
2. **Een gedeeld logbestand onder `results/logs/`** — één bestand per
   proces (`run_{YYYYmmdd_HHMMSS}.log`), aangemaakt op het moment dat het
   eerste script in dat proces een logger opvraagt. Draai je
   `run_pipeline.py`, dan komen de logregels van `010`, `020` én `030` in
   diezelfde ene, chronologisch geordende file terecht — handig om een
   onbeheerde run achteraf terug te lezen, of om te zien wat er precies
   gebeurde tijdens de `k`-sweep van `005`. Het pad van het huidige
   logbestand is ook beschikbaar als `logging_utils.LOG_FILE`.

   Elk logbestand begint met een kort header-blok dat vastlegt **welke
   aanroep het proces gestart heeft**, bijvoorbeeld:

   ```
   ================================================================================
   Run started : 2026-07-21 14:12:30
   Entry point : run_pipeline.py
   Command     : run_pipeline.py
   ================================================================================
   ```

   Zo kun je een logbestand achteraf altijd herleiden tot `run_pipeline.py`,
   `run_cluster_selection.py`, of een los gedraaide stap (bijvoorbeeld
   `python 030-pca-pipeline.py`) — dat is anders niet af te lezen uit de
   interleaved logregels van meerdere stages.

Wil je meer detail zien (bijvoorbeeld de exacte verdeling van ontbrekende
waarden), zet dan het niveau op `DEBUG`:

```python
import logging
logging.getLogger("010-gmm").setLevel(logging.DEBUG)
```

Dit geldt voor beide handlers (stdout én het logbestand).

---

## Bekende ontwerpkeuzes en beperkingen

Deze punten zijn bewuste keuzes of bekende beperkingen — geen bugs, maar
wel dingen om in gedachten te houden:

- **Globale mediaan-imputatie.** Ontbrekende waarden worden opgevuld met de
  mediaan over *alle* landen samen, vóór de opsplitsing per land. Verschillen
  de verdelingen sterk per land, dan kan dit een lichte vertekening geven
  voor kleinere landen. Wil je dit per land doen, pas dan
  `load_and_clean()` in `data_loading.py` aan (bijvoorbeeld met
  `df.groupby(config.COUNTRY_COL).transform(...)`).
- **`n_init` verschilt tussen fase 1 en fase 2.** De verkennende sweep
  (`005`) gebruikt `CLUSTER_SELECTION_N_INIT = 5` in plaats van de 10
  herstarts die de productie-fit (`010`) gebruikt, puur om de sweep
  behapbaar te houden (er worden negen keer zoveel modellen gefit). Dit kan
  in theorie tot een net iets andere silhouette-score leiden dan een fit
  met `n_init=10` zou geven.
- **Silhouette-score wordt eventueel op een steekproef berekend.**
  `CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` (standaard 5000 rijen) begrenst
  hoeveel rijen worden meegenomen in de silhouette-berekening, omdat deze
  metric kwadratisch schaalt met het aantal rijen. Zet op `None` voor een
  exacte berekening op alle rijen (kan traag zijn bij grote landen).
- **BIC/AIC zijn optioneel.** Deze worden alleen toegevoegd aan
  `cluster_selection.csv` als `tgmm`'s `GaussianMixture`-klasse `.bic()`
  en/of `.aic()` methodes aanbiedt. Is dat niet het geval, dan ontbreken die
  kolommen simpelweg en kun je varen op de silhouette-score.

---

## Veelvoorkomende problemen

**`FileNotFoundError: ... run 005-cluster-selection-pipeline.py first`**
Je probeert `006` te draaien zonder dat `results/cluster_selection.csv`
bestaat. Draai eerst `005`, of gebruik `run_cluster_selection.py` die beide
in de juiste volgorde draait.

**`FileNotFoundError: ... run 010-gmm-pipeline.py first`**
Je probeert `020` of `030` te draaien zonder dat de bijbehorende
outputbestanden van `010` bestaan. Draai eerst `010` (of `run_pipeline.py`).

**Waarschuwing "No GMM_N_COMPONENTS entry for '<land>'"**
Er staat geen waarde voor dat land in het `GMM_N_COMPONENTS`-dictionary in
`config.py`. De pipeline valt terug op `GMM_N_COMPONENTS_DEFAULT`, maar
controleer of dat de bedoeling is — voeg anders een expliciete waarde toe.

**"k=... collapsed to N actual cluster(s)"** (in `005`)
Bij sommige waarden van `k` kan een GMM-component "leeg" eindigen (geen
enkele rij krijgt dat label toegewezen). De silhouette-score is dan niet
gedefinieerd voor die `k` en wordt als `NaN` weggeschreven — dat specifieke
punt ontbreekt dan in de plot.

**Trage runs bij `005`**
Verlaag `CLUSTER_SELECTION_K_MAX`, verhoog niet onnodig
`CLUSTER_SELECTION_N_INIT`, en overweeg
`CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` te verlagen voor grote landen.

---

## Pipeline uitbreiden

- **Nieuw land toevoegen:** voeg de landcode toe aan `config.LANDEN` én aan
  het `GMM_N_COMPONENTS`-dictionary (of laat het terugvallen op de default).
- **Features aanpassen:** pas `prepare_features()` aan in `data_loading.py`
  — deze wordt door zowel `005` als `010` gebruikt, dus een wijziging hier
  geldt automatisch voor beide.
- **Extra metrics in de cluster-selectie:** breid `_evaluate_k()` in `005`
  uit; voeg de kolomnaam toe aan het resultaat-dictionary en pas `006` aan
  om de nieuwe metric ook te plotten.
- **Los één stap draaien:** elk genummerd script heeft een
  `if __name__ == "__main__": run()`-blok en kan dus los gedraaid worden,
  bijvoorbeeld `python 030-pca-pipeline.py`, zonder de orchestrators te
  gebruiken.