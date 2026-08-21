# Consumer-segmentatie pipeline

Deze pipeline segmenteert consumenten per land met een Gaussian Mixture Model (GMM),
bepaalt hoeveel segmenten (clusters) daarvoor optimaal zijn, en berekent statistieken
en een PCA-reductie over de resulterende segmenten.

De pipeline is opgesplitst in genummerde stappen (`005`, `006`, `007`, `010`, `020`)
die je los kunt draaien, of via twee orchestrator-scripts in de juiste volgorde
achter elkaar: eerst verkennen, dan pas de volledige productie-run.

---

## Inhoudsopgave

1. [Snelstart](#snelstart)
2. [Vereisten](#vereisten)
3. [Bestandsstructuur](#bestandsstructuur)
4. [De twee fases van de workflow](#de-twee-fases-van-de-workflow)
5. [Feature-count sweep](#feature-count-sweep)
6. [Configuratie (`config.py`)](#configuratie-configpy)
7. [De stappen in detail](#de-stappen-in-detail)
8. [Outputbestanden](#outputbestanden)
9. [Logging](#logging)
10. [Bekende ontwerpkeuzes en beperkingen](#bekende-ontwerpkeuzes-en-beperkingen)
11. [Veelvoorkomende problemen](#veelvoorkomende-problemen)
12. [Pipeline uitbreiden](#pipeline-uitbreiden)

---

## Snelstart

```bash
# Fase 1 — verkennen: hoeveel clusters zijn optimaal per land?
python run_cluster_selection.py
# Genereert automatisch gmm_n_components_feat<N>.json met de beste k per land.
# Controleer en pas dit bestand aan als je een andere keuze wilt.

# Fase 2 — productie: de volledige pipeline draaien met die keuzes
python run_pipeline.py
```

Wil je alle drie feature-varianten (12 / 30 / 32 features) in één keer sweepen:

```bash
python run_feature_sweep.py
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
├── run_cluster_selection.py                   # Orchestrator FASE 1: draait 005 + 006 + 007
├── run_pipeline.py                            # Orchestrator FASE 2: draait 010 + 020
├── run_feature_sweep.py                       # Draait run_cluster_selection.py voor alle drie feature-sets
│
├── 005-cluster-selection-pipeline.py          # Sweept k per land over meerdere covariantie-types
├── 006-visualise-cluster-selection-pipeline.py # Plot silhouette/Davies-Bouldin/Calinski-Harabasz vs. k per land
├── 007-update-config-from-cluster-selection.py # Schrijft beste k + covariantie per land weg als JSON
├── 010-gmm-pipeline.py                        # Productie-fit: GMM + PCA per land
├── 020-stats-pipeline.py                      # Clusterstatistieken per land
│
├── gmm_n_components_feat12.json               # Auto-gegenereerd door 007 (12-feature run)
├── gmm_n_components_feat30.json               # Auto-gegenereerd door 007 (30-feature run)
├── gmm_n_components_feat32.json               # Auto-gegenereerd door 007 (32-feature run)
│
├── data/
│   └── amount_of_orders_data.csv              # Ruwe inputdata (zelf aan te leveren)
│
└── results/                                   # Wordt automatisch aangemaakt
    ├── cluster_selection_feat12_{timestamp}.csv
    ├── cluster_selection_feat30_{timestamp}.csv
    ├── cluster_selection_feat32_{timestamp}.csv
    ├── pca_scores_feat12.csv                  # PCA-scores uit de cluster-selectie sweep (005)
    ├── pca_loadings_feat12.csv                # PCA-loadings uit de cluster-selectie sweep (005)
    ├── figures/
    │   └── cluster_selection_{land}_feat12.png # Output van 006, één plot per land per feature-set
    ├── consumers_{land}.csv                   # Output van 010, één bestand per land
    ├── consumers_met_segmenten_per_land.csv   # Output van 010, alle landen samengevoegd
    ├── consumers_met_pca.csv                  # PCA-scores gebruikt voor clustering (010)
    ├── PCA.txt                                # Leesbaar PCA-rapport per land (010)
    ├── stats_{timestamp}.csv                  # Output van 020
    └── logs/
        └── run_{timestamp}.log                # Eén logbestand per proces/run, alle stappen samen
```

**Let op de nummering:** de stapnummers geven de logische volgorde weer, niet per se
de importvolgorde in Python (bestandsnamen met een koppelteken en een cijfer
vooraan kun je niet direct `import`eren — de orchestrators laden ze daarom via
`importlib` op basis van bestandspad).

**Noot over 030-pca-pipeline.py:** deze stap bestaat niet meer als apart script.
PCA wordt nu uitgevoerd binnen `010-gmm-pipeline.py`, zodat de PCA-ruimte die
gerapporteerd wordt exact dezelfde is als die voor clustering werd gebruikt.
`run_pipeline.py` draait 030 dus niet meer.

---

## De twee fases van de workflow

### Fase 1 — Verkennen: hoeveel clusters zijn optimaal?

```bash
python run_cluster_selection.py
```

Dit draait drie stappen achter elkaar:

1. **`005-cluster-selection-pipeline.py`** — laadt de ruwe (opgeschoonde) data en
   fit per land een GMM voor elk `k` in `config.CLUSTER_SELECTION_K_MIN..K_MAX`
   (standaard 3 t/m 6), over **alle geconfigureerde covariantie-types**
   (`full`, `diag`, `spherical`, `tied_full`, `tied_diag`, `tied_spherical`).
   Elke fit wordt gescoord met de silhouette-score, Davies-Bouldin-score en
   Calinski-Harabasz-score. Ook BIC/AIC worden berekend als het model dat
   ondersteunt. Daarnaast voert `005` per land een PCA uit op de
   gestandaardiseerde features en slaat scores en loadings op — handig om
   features te spotten die nauwelijks bijdragen aan de clustering.
2. **`006-visualise-cluster-selection-pipeline.py`** — leest die resultaten
   en tekent per land drie subplots: silhouette-score, Davies-Bouldin en
   Calinski-Harabasz, elk met één lijn per covariantie-type.
3. **`007-update-config-from-cluster-selection.py`** — leest de nieuwste
   `cluster_selection_feat<N>_*.csv` per feature-set en schrijft de beste
   combinatie van `k`, covariantie-type en initialisatie per land weg naar
   `gmm_n_components_feat<N>.json`. Dit bestand wordt door `config.py` en
   stap `010` geladen. Controleer de inhoud na afloop — de script kiest op
   basis van hoogste silhouette (daarna laagste Davies-Bouldin), maar
   zakelijke interpretatie kan leiden tot een andere keuze.

**Belangrijk:** deze fase draait *voordat* de productie-GMM (`010`) draait
— hij hangt niet af van `010`'s output.

Na afloop:

- Bekijk de plots in `results/figures/` en de CSV in `results/`.
- Er is geen "juist" antwoord dat het script automatisch kiest. Een lagere
  silhouette-score kan een aantal segmenten opleveren dat beter uitlegbaar
  is aan de business. Gebruik de plots en de logging als hulpmiddel.
- Pas `gmm_n_components_feat<N>.json` handmatig aan als je een andere keuze
  wilt dan wat `007` heeft weggeschreven.

### Fase 2 — Productie: de volledige pipeline draaien

Zorg dat `gmm_n_components_feat<N>.json` gevuld is (dit doet `007` automatisch).
`config.py` laadt het JSON-bestand dat overeenkomt met de actieve `FEATURE_SET`.

```bash
python run_pipeline.py
```

Dit draait:

1. **`010-gmm-pipeline.py`** — de definitieve GMM-fit per land, met het
   aantal clusters, het covariantie-type en de beste initialisatie uit het
   JSON-configuratiebestand. Staat een land niet in dat bestand, dan valt de
   pipeline terug op `config.GMM_N_COMPONENTS_DEFAULT` én geeft een
   waarschuwing. Stap `010` voert ook de PCA-rapportage uit (voorheen stap
   `030`): de PCA die daadwerkelijk voor clustering is gebruikt wordt nu ook
   voor rapportage weggeschreven, zodat beide altijd consistent zijn.
2. **`020-stats-pipeline.py`** — berekent clusterstatistieken per land op
   basis van de segmentlabels uit stap `010`.

---

## Feature-count sweep

```bash
python run_feature_sweep.py
```

Draait `run_cluster_selection.py` drie keer achter elkaar als subproces — één
keer per feature-variant (`FEATURE_SET=12`, `30`, `32`). Elk subproces
importeert `config.py` opnieuw met de juiste omgevingsvariabele, zodat
outputbestanden niet over elkaar heen worden geschreven:

| `FEATURE_SET` | Features | Uitgesloten kolommen |
|---|---|---|
| `12` | 12 samengestelde GMM-features | Alle 21 extra kolommen |
| `30` | 12 curated + 18 seizoens-/campagnekolommen | Alleen de jaarlijkse totalen + dubbele orderteller |
| `32` | 12 curated + 18 seizoenskolommen + 2 jaarlijkse totalen | Alleen de dubbele orderteller |

Na de sweep zijn er drie `gmm_n_components_feat<N>.json`-bestanden. Om de
productie-pipeline met een specifieke feature-set te draaien:

```bash
FEATURE_SET=30 python run_pipeline.py
```

`config.py` laadt dan automatisch `gmm_n_components_feat30.json`.

---

## Configuratie (`config.py`)

Alle instellingen staan op één plek, zodat je ze niet in meerdere scripts
hoeft aan te passen.

| Instelling | Betekenis |
|---|---|
| `LANDEN` | Lijst van landcodes die door elke stap verwerkt worden |
| `FEATURE_SET` | Actieve feature-variant (`"12"` / `"30"` / `"32"`), instelbaar via env var |
| `ID_COL` | Kolomnaam van de unieke consument-identifier |
| `COUNTRY_COL` | Kolomnaam die het land van een rij aangeeft in de brondata |
| `LAND_COL` | Kolomnaam `"land"` zoals gebruikt in resultaattabellen |
| `EXCLUDE_TERMS` | Substrings (bv. `"segment"`) — kolommen die dit bevatten worden uitgesloten van numerieke modellering |
| `GMM_INPUT_PATH` | Pad naar de ruwe inputdata |
| `GMM_N_COMPONENTS_DEFAULT` | Fallback-waarde als een land niet in het JSON-configuratiebestand staat |
| `COVARIANCE_TYPE` | Lijst van covariantie-types die `005` sweept |
| `CLUSTER_SELECTION_K_MIN` / `K_MAX` | Bereik van te testen clusteraantallen in fase 1 |
| `CLUSTER_SELECTION_N_INIT` | Aantal herstarts per GMM-fit in fase 1 (lager dan productie, voor snelheid) |
| `CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` | Max. rijen voor de silhouette-berekening (`None` = alle rijen) |
| `PCA_N_COMPONENTS` | Aantal PCA-componenten (≥1 = exact aantal, <1 = verklaarde variantie-drempel) |
| `PCA_VARIANCE_TARGET` | Drempelwaarde die in het PCA-rapport wordt gerapporteerd |

**GMM-configuratie per land** wordt niet meer direct in `config.py` ingevoerd.
Stap `007` schrijft `gmm_n_components_feat<N>.json` en `config.py` laadt dat
automatisch. De functies `get_n_components(land)`, `get_covariance_type(land)`
en `get_best_init_setup(land)` lezen uit dat JSON, met een fallback en
waarschuwing als een land ontbreekt.

---

## De stappen in detail

### `data_loading.py`

Gedeeld door `005` en `010`, zodat beide exact dezelfde featurematrix per land
gebruiken. Twee functies:

- **`load_and_clean(pad)`** — laadt de ruwe CSV, coerceert `KOOPKRACHT` naar
  numeriek en imputeert ontbrekende waarden met de **kolommediaan per land**.
- **`prepare_features(df_land)`** — verwijdert ID-, land-, categorische en
  segment-gerelateerde kolommen, zodat alleen echte modelfeatures overblijven.

### `005-cluster-selection-pipeline.py`

- **Input:** ruwe data via `load_and_clean`.
- **Werking:** per covariantie-type, per land, per `k` in het geconfigureerde
  bereik: een GMM fitten en scoren met silhouette, Davies-Bouldin en
  Calinski-Harabasz (en BIC/AIC als het model dat ondersteunt). Voert ook
  een PCA uit op de gestandaardiseerde features en slaat scores en loadings op.
  De GMM-fit zelf loopt op de PCA-gereduceerde representatie.
- **Output:**
  - `results/cluster_selection_feat<N>_{timestamp}.csv`
  - `results/pca_scores_feat<N>.csv`
  - `results/pca_loadings_feat<N>.csv`

### `006-visualise-cluster-selection-pipeline.py`

- **Input:** `results/cluster_selection_feat<N>_{timestamp}.csv`.
- **Output:** `results/figures/cluster_selection_{land}_feat<N>.png` — drie
  subplots per land (silhouette, Davies-Bouldin, Calinski-Harabasz), elk met
  één lijn per covariantie-type.

### `007-update-config-from-cluster-selection.py`

- **Input:** alle `cluster_selection_feat<N>_*.csv`-bestanden in `results/`,
  gegroepeerd op feature-tag.
- **Werking:** kiest per land de combinatie van `k`, covariantie-type en
  initialisatie met de hoogste silhouette-score (bij gelijkheid: laagste
  Davies-Bouldin). Schrijft het resultaat weg als JSON.
- **Output:** `gmm_n_components_feat<N>.json` per feature-set.

### `010-gmm-pipeline.py`

- **Input:** ruwe data via `load_and_clean` + `gmm_n_components_feat<N>.json`.
- **Werking:** per land een GMM fitten met het aantal clusters, covariantie-type
  en beste initialisatie uit het JSON-bestand. De `StandardScaler` wordt **per
  land** apart gefit — dit is bewust, anders vergelijk je landen onderling
  in plaats van consumenten binnen een land te segmenteren. De PCA die voor
  clustering gebruikt wordt, wordt ook voor rapportage bewaard (de PCA-output
  van deze stap is dus altijd consistent met de segmenten).
- **Output:**
  - `results/consumers_{land}.csv` — per land, met `segment` en
    `segment_{i}_kans` toegevoegd.
  - `results/consumers_met_segmenten_per_land.csv` — alle landen samen, met
    `segment_globaal` (`{land}_{segment}`).
  - `results/consumers_met_pca.csv` — PCA-scores gebruikt voor clustering.
  - `results/PCA.txt` — leesbaar rapport met verklaarde variantie, loadings
    en top features per component, per land.

### `020-stats-pipeline.py`

- **Input:** de per-land bestanden uit stap `010`.
- **Werking:** berekent per land clusterstatistieken: grootte per cluster,
  beschrijvende statistieken per feature, silhouette per cluster, en overall
  silhouette/Calinski-Harabasz/Davies-Bouldin. De helpers hiervoor
  (`compute_cluster_statistics`, `flatten_cluster_statistics`, etc.) zijn
  ingebakken in dit script — er is geen externe `utils.py` nodig.
- **Output:** `results/stats_{timestamp}.csv`.

---

## Outputbestanden

| Bestand | Gemaakt door | Inhoud |
|---|---|---|
| `results/cluster_selection_feat<N>_{timestamp}.csv` | `005` | Silhouette/Davies-Bouldin/Calinski-Harabasz/BIC/AIC per covariantie-type per land per geteste `k` |
| `results/pca_scores_feat<N>.csv` | `005` | PCA-scores per rij, per land, per covariantie-type |
| `results/pca_loadings_feat<N>.csv` | `005` | PCA-loadings per feature per component |
| `results/figures/cluster_selection_{land}_feat<N>.png` | `006` | Elleboogplots per land, één lijn per covariantie-type |
| `gmm_n_components_feat<N>.json` | `007` | Beste `k`, covariantie-type en initialisatie per land |
| `results/consumers_{land}.csv` | `010` | Ruwe data + segmentlabel + segmentkansen, per land |
| `results/consumers_met_segmenten_per_land.csv` | `010` | Alle landen samen + `segment_globaal` |
| `results/consumers_met_pca.csv` | `010` | ID + PCA-scores (zelfde PCA als gebruikt voor clustering) |
| `results/PCA.txt` | `010` | Leesbaar PCA-rapport per land |
| `results/stats_{timestamp}.csv` | `020` | Clusterstatistieken per land |
| `results/logs/run_{timestamp}.log` | elke stap | Alle logregels van het proces dat je startte |

---

## Logging

Elk script gebruikt `logging_utils.get_logger(naam)` voor consistente,
tijdgestempelde logregels. Elke logger schrijft naar **twee** plekken:

1. **stdout** — om een run live te kunnen volgen.
2. **Een gedeeld logbestand onder `results/logs/`** — één bestand per
   proces (`run_{YYYYmmdd_HHMMSS}.log`). Draai je `run_pipeline.py`, dan
   komen de logregels van `010` én `020` in diezelfde ene, chronologisch
   geordende file terecht. Het pad van het huidige logbestand is beschikbaar
   als `logging_utils.LOG_FILE`.

Elk logbestand begint met een kort header-blok:

```
================================================================================
Run started : 2026-08-18 09:04:12
Entry point : run_cluster_selection.py
Command     : run_cluster_selection.py
================================================================================
```

Zo kun je een logbestand achteraf altijd herleiden tot het script dat het
gestart heeft.

Meer detail (bijvoorbeeld de exacte verdeling van ontbrekende waarden):

```python
import logging
logging.getLogger("010-gmm").setLevel(logging.DEBUG)
```

---

## Bekende ontwerpkeuzes en beperkingen

- **Mediaan-imputatie per land.** Ontbrekende waarden worden gevuld met de
  mediaan per land (via `groupby`). Dit is bewust: waarden worden zo vergeleken
  met het land-specifieke gemiddelde, niet met het globale gemiddelde.
- **`n_init` verschilt tussen fase 1 en fase 2.** De verkennende sweep
  (`005`) gebruikt `CLUSTER_SELECTION_N_INIT = 5` in plaats van de volledige
  hoeveelheid herstarts die de productie-fit (`010`) gebruikt. Dit houdt de
  sweep behapbaar — er worden immers veel meer modellen gefit — maar kan in
  theorie tot een iets andere silhouette-score leiden.
- **Silhouette-score wordt eventueel op een steekproef berekend.**
  `CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` (standaard 5000 rijen) begrenst
  hoeveel rijen worden meegenomen, omdat silhouette kwadratisch schaalt met
  het aantal rijen. Zet op `None` voor een exacte berekening (kan traag zijn).
- **GMM-fit op PCA-gereduceerde features.** Zowel `005` als `010` clusteren
  op de PCA-scores, niet op de gestandaardiseerde ruwe features. Dit helpt
  de covariantieberekening van de GMM in hogere dimensies stabieler te maken.
- **`PCA_N_COMPONENTS ≥ 1` behoudt alle features.** Alleen waarden < 1
  worden als variantie-drempel geïnterpreteerd. Standaard staat dit op `12`
  (= alle features bij een 12-feature run).
- **`007` kiest automatisch, maar heeft menselijke review nodig.** De beste
  `k` per land wordt bepaald op silhouette (dan Davies-Bouldin), maar
  zakelijke interpretatie kan een andere keuze rechtvaardigen. Pas
  `gmm_n_components_feat<N>.json` handmatig aan als dat het geval is.

---

## Veelvoorkomende problemen

**`FileNotFoundError: gmm_n_components_feat12.json not found`**
Draai eerst `run_cluster_selection.py` (of `007-update-config-from-cluster-selection.py`
los). Het JSON-bestand wordt pas aangemaakt na de cluster-selectie sweep.

**`FileNotFoundError: ... run 005-cluster-selection-pipeline.py first`**
Je probeert `006` te draaien zonder dat een `cluster_selection_feat<N>_*.csv`
bestaat. Draai eerst `005`, of gebruik `run_cluster_selection.py`.

**`FileNotFoundError: ... run 010-gmm-pipeline.py first`**
Je probeert `020` te draaien zonder dat de bijbehorende outputbestanden van
`010` bestaan. Draai eerst `010` (of `run_pipeline.py`).

**Waarschuwing "No GMM_N_COMPONENTS entry for '<land>'"**
Er staat geen waarde voor dat land in het JSON-configuratiebestand. De
pipeline valt terug op `GMM_N_COMPONENTS_DEFAULT` — voeg anders een
expliciete waarde toe aan `gmm_n_components_feat<N>.json`.

**"k=... collapsed to N actual cluster(s)"** (in `005`)
Een GMM-component eindigde leeg (geen rij kreeg dat label). De silhouette-score
is dan niet gedefinieerd en wordt als `NaN` weggeschreven — dat punt ontbreekt
in de plot.

**Trage runs bij `005`**
Verlaag `CLUSTER_SELECTION_K_MAX`, beperk het aantal covariantie-types in
`config.COVARIANCE_TYPE`, verlaag `CLUSTER_SELECTION_N_INIT`, of verlaag
`CLUSTER_SELECTION_SILHOUETTE_SAMPLE_SIZE` voor grote landen.

---

## Pipeline uitbreiden

- **Nieuw land toevoegen:** voeg de landcode toe aan `config.LANDEN`. Na de
  volgende cluster-selectie sweep vult `007` automatisch het JSON-bestand aan.
- **Features aanpassen:** pas `prepare_features()` aan in `data_loading.py`
  — beide `005` en `010` gebruiken deze functie, dus een wijziging geldt
  automatisch voor beide. Vergeet niet `FEATURE_SET` en
  `GMM_EXTRA_EXCLUDE_COLS_VARIANTS` in `config.py` mee te updaten.
- **Extra covariantie-types testen:** voeg ze toe aan `config.COVARIANCE_TYPE`.
  `005` en `006` verwerken ze automatisch.
- **Extra metrics in de cluster-selectie:** breid `_evaluate_k()` in `005`
  uit en voeg de kolomnaam toe aan de constanten in `config.py`. Pas `006`
  aan om de nieuwe metric te plotten.
- **Los één stap draaien:** elk genummerd script heeft een
  `if __name__ == "__main__": run()`-blok en kan los gedraaid worden,
  bijvoorbeeld `python 020-stats-pipeline.py`.
