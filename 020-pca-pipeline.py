import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

# ------------------- CONFIG -------------------
INPUT_PATH = "results/consumers_met_segmenten_per_land.csv"   # <- pas aan
OUTPUT_CSV = "results/consumers_met_pca.csv"
OUTPUT_TXT = "results/PCA.txt"
LANDEN = [ "NL", "BE", "FR", "DE", "GB","ES"]
EXCLUDE_TERMS = ["segment"]  # <- kolommen die deze term bevatten worden uitgesloten van PCA
N_COMPONENTS = 2
TOP_N_FEATURES = 15
LAND_COL = 'prd_country'
# -----------------------------------------------

df = pd.read_csv(INPUT_PATH)

if LAND_COL not in df.columns:
    raise ValueError(f"Kolom '{LAND_COL}' niet gevonden in df. Beschikbare kolommen: {list(df.columns)}")

# kolommen die uitgesloten worden van PCA (segment-/clusterlabels e.d.)
exclude_cols = [c for c in df.columns if any(term in c.lower() for term in EXCLUDE_TERMS)]
print(f"Uitgesloten van PCA ({len(exclude_cols)} kolommen): {exclude_cols}\n")

all_pca_scores = []  # verzamelt de PCA-scores per land, om aan het einde samen te voegen
txt_blocks = []       # verzamelt de tekstblokken voor PCA.txt, per land

for land, group in df.groupby(LAND_COL):
    print(f"=== Land: {land} (n={len(group)}) ===")

    numeric_cols = group.select_dtypes(include="number").drop(columns=exclude_cols, errors="ignore")

    # afhandelen van ontbrekende waarden
    n_missing = numeric_cols.isna().sum().sum()
    if n_missing > 0:
        missing_distribution = numeric_cols.isna().sum()
        kolommen_met_missing = numeric_cols.columns[numeric_cols.isna().any()].tolist()
        print(f"Let op: {n_missing} ontbrekende waarden gevonden in {kolommen_met_missing}, opgevuld met kolomgemiddelde.\n")
        numeric_cols = numeric_cols.fillna(numeric_cols.mean(numeric_only=True))
    else:
        print("Geen ontbrekende waarden gevonden.\n")

    # landen met te weinig rijen voor het gevraagde aantal componenten overslaan
    if len(numeric_cols) <= N_COMPONENTS:
        print(f"Overgeslagen: te weinig rijen ({len(numeric_cols)}) voor {N_COMPONENTS} componenten.\n")
        continue

    # standaardiseren vóór PCA (verplicht bij gemengde eenheden: geld, aantallen, vlaggen, indices, etc.)
    scaler = StandardScaler()
    numeric_scaled = pd.DataFrame(
        scaler.fit_transform(numeric_cols),
        columns=numeric_cols.columns,
        index=numeric_cols.index,
    )

    pca = PCA(n_components=N_COMPONENTS)
    pca_scores = pca.fit_transform(numeric_scaled)

    # PC-scores als dataframe, met dezelfde index als de oorspronkelijke groep -> sluit later goed aan bij samenvoegen
    pca_df = pd.DataFrame(
        pca_scores,
        columns=[f"PC{i+1}" for i in range(pca.n_components_)],
        index=numeric_cols.index,
    )
    all_pca_scores.append(pca_df)

    # --- statistieken voor dit land ---
    expl_var = pca.explained_variance_
    expl_var_rat = pca.explained_variance_ratio_
    cum_var = expl_var_rat.cumsum()
    singular_values = pca.singular_values_

    loadings = pd.DataFrame(
        pca.components_.T,
        columns=[f"PC{i+1}" for i in range(pca.n_components_)],
        index=numeric_cols.columns,
    )

    top_features = ""
    for col in loadings.columns:
        sorted_loadings = loadings[col].abs().sort_values(ascending=False)
        top_features += f"Top {TOP_N_FEATURES} kenmerken voor {col}:\n{loadings.loc[sorted_loadings.index[:TOP_N_FEATURES], col]}\n\n"

    # aantal componenten nodig voor 90% verklaarde variantie (ongebonden PCA, alleen ter referentie)
    pca_full = PCA().fit(numeric_scaled)
    cum_full = pca_full.explained_variance_ratio_.cumsum()
    n_for_90 = int((cum_full >= 0.90).argmax() + 1)

    block = (
        f"=== Land: {land} (n={len(group)}) ===\n"
        f"Aantal samples: {numeric_cols.shape[0]}, Aantal features: {numeric_cols.shape[1]}\n"
        f"Gebruikte features: {list(numeric_cols.columns)}\n\n"
        f"Verklaarde variantie PCA:                {expl_var}\n"
        f"Verklaarde variantie ratio PCA:          {expl_var_rat}\n"
        f"Cumulatieve verklaarde variantie ratio:  {cum_var}\n"
        f"Singuliere waarden PCA:                  {singular_values}\n"
        f"Aantal componenten nodig voor 90% variantie: {n_for_90} (van {numeric_cols.shape[1]} features)\n\n"
        f"PCA loadings (gewicht per component per feature):\n{loadings}\n\n"
        f"{top_features}"
        f"{'-'*80}\n\n"
    )
    print(block)
    txt_blocks.append(block)

# schrijf de statistieken van alle landen naar één tekstbestand
with open(OUTPUT_TXT, "w") as outfile:
    outfile.write("\n".join(txt_blocks))

# voeg de PCA-scores van alle landen samen en merge terug in de originele df (index blijft behouden per groep)
pca_scores_all = pd.concat(all_pca_scores)
df_with_pca = df.join(pca_scores_all)  # join op index, veiliger dan concat als de rijvolgorde is veranderd

df_with_pca.to_csv(OUTPUT_CSV, index=False)
print(f"Klaar. Output weggeschreven naar {OUTPUT_CSV} en {OUTPUT_TXT}")