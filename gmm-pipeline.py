"""
Volledige pipeline: tabel -> one-hot encoding -> GMM (tgmm) -> labels terugkoppelen aan originele rijen.

Benodigde packages installeren (indien nodig):
    pip install pandas scikit-learn torch tgmm matplotlib
"""

import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from tgmm import GaussianMixture

# ---------------------------------------------------------------------------
# 1. DATA INLADEN
# ---------------------------------------------------------------------------
INPUT_PATH = "data/amount_of_orders_data.csv"          # <- pas aan naar jouw bestand
ID_COLS = ["master_person_key_md5"]             # <- kolommen die je NIET wilt modelleren
N_COMPONENTS = 6                                # <- gewenst aantal segmenten

df = pd.read_csv(INPUT_PATH)
# Koopkracht wordt verkeerd ingeladen als string, dus eerst converteren naar numeriek (float)
df['KOOPKRACHT'] = pd.to_numeric(df['KOOPKRACHT'].str.strip(), errors="coerce")

# Bewaar een ongewijzigde kopie van de originele tabel om later de labels aan te koppelen
df_original = df.copy()

print(f"Data ingeladen: {len(df)} rijen, {len(df.columns)} kolommen.")
print(f"Kolommen: {df.columns.tolist()}\n")


LANDEN = [ "NL", "BE", "FR", "DE", "GB","ES"]


# ---------------------------------------------------------------------------
# 2. FUNCTIE OM ÉÉN LAND TE VERWERKEN EN TE FITTEN
# ---------------------------------------------------------------------------
def fit_gmm_voor_land(df_land: pd.DataFrame, n_components: int) -> pd.DataFrame:
    """Fit een GMM op de rijen van één land en geef een df terug met labels/kansen."""

    # Categorisch vs numeriek
    categorical_cols = df_land.select_dtypes(exclude="number").columns.tolist()
    numeric_cols = df_land.select_dtypes(include="number").columns.tolist()
    print(f"Numerieke kolommen ({len(numeric_cols)}): {numeric_cols}")

    # Kolommen die niet gemodelleerd worden (ID + land zelf, want die is nu constant)
    kolommen_uitsluiten = ID_COLS + ['prd_country', 'order_number_functional_all'] + categorical_cols
    df_features = df_land.drop(columns=kolommen_uitsluiten)
    print(f"Features na uitsluiten van {kolommen_uitsluiten}: {df_features.columns.tolist()}\n")
    
    # # Categorisch vs numeriek
    # categorical_cols = df_features.select_dtypes(exclude="number").columns.tolist()
    # numeric_cols = df_features.select_dtypes(include="number").columns.tolist()
    # print(f"Numerieke kolommen ({len(numeric_cols)}): {numeric_cols}")

    # Ontbrekende waarden opvullen, anders werkt GMM niet. Hier vullen we op met het gemiddelde van de kolom (voor numerieke kolommen).
    n_missing = df_features.isna().sum().sum()
    missing_distribution = df_features.isna().sum()
    
    if n_missing > 0:
        print(f"Let op: distributie van ontbrekende waarden per kolom:\n{missing_distribution[missing_distribution > 0]}\n")
        kolommen_met_missing = df_features.columns[df_features.isna().any()].tolist()
        print(f"Let op: {n_missing} ontbrekende waarden gevonden in {kolommen_met_missing}, opgevuld met kolomgemiddelde.\n")
    else:
        print("Geen ontbrekende waarden gevonden.\n")
    df_features = df_features.fillna(df_features.mean(numeric_only=True))


    # Schalen — BELANGRIJK: per land opnieuw fitten, niet globaal,
    # anders vergelijk je landen tegen elkaar in plaats van binnen elkaar te segmenteren
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_features.values)
    print(f"Features geschaald (StandardScaler), vorm: {X_scaled.shape}.\n")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    X_tensor = torch.tensor(X_scaled, dtype=torch.float32, device=device)
    print(f"Tensor aangemaakt op device: {device}.\n")

    # GMM fitten
    print(f"GMM trainen met {n_components} componenten...")
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type="diag",
        init_means="kmeans",
        n_init=10,
        random_state=0,
        reg_covar=1e-4,
    )

    gmm.fit(X_tensor)
    print("GMM getraind.")
    labels = gmm.predict(X_tensor).cpu().numpy()
    probs = gmm.predict_proba(X_tensor).cpu().numpy()

    # Resultaten terugkoppelen aan de originele rijen van dit land
    df_result_land = df_land.copy()
    df_result_land["segment"] = labels

    prob_cols = [f"segment_{i}_kans" for i in range(n_components)]
    df_result_land[prob_cols] = probs
    print(f"Segmentverdeling: {pd.Series(labels).value_counts().to_dict()}")

    return df_result_land


# ---------------------------------------------------------------------------
# 3. PER LAND LOOPEN — RESULTATEN OPSLAAN IN EEN DICT (1 DF PER LAND)
# ---------------------------------------------------------------------------
dfs_per_land = {}   # <- hier krijgt elk land zijn eigen df, bv. dfs_per_land["NL"]

for land in LANDEN:
    print(f"\n{20*'='} Verwerken van {land} {20*'='}")
    df_land = df[df['prd_country'] == land]
 
    if df_land.empty:
        print(f"Let op: geen rijen gevonden voor {land}, wordt overgeslagen.")
        continue
 
    print(f"{len(df_land)} rijen gevonden voor {land}.")
    dfs_per_land[land] = fit_gmm_voor_land(df_land, N_COMPONENTS)
    print(f"Klaar met {land}.")


# Nu heb je losse dataframes, elk met hun eigen GMM-resultaten:
#   dfs_per_land["NL"]
#   dfs_per_land["BE"]
#   dfs_per_land["FR"]
#   dfs_per_land["DE"]
#   dfs_per_land["UK"]
#   dfs_per_land["ES"]

print(f"\nAlle landen verwerkt: {list(dfs_per_land.keys())}")
# Los opslaan per land, bijvoorbeeld:
print("\nWegschrijven van losse CSV's per land...")
for land, df_land_resultaat in dfs_per_land.items():
    bestandsnaam = f"results/consumers_{land}.csv"
    df_land_resultaat.to_csv(bestandsnaam, index=False)
    print(f"  {bestandsnaam} opgeslagen ({len(df_land_resultaat)} rijen).")


# ---------------------------------------------------------------------------
# 4. (OPTIONEEL) ALLE LANDEN SAMEN BEKIJKEN IN ÉÉN DF
# ---------------------------------------------------------------------------
# Handig voor een totaaloverzicht — de losse dfs in dfs_per_land blijven
# gewoon beschikbaar, dit is puur een extra gecombineerde versie ernaast.
print("\nAlle landen samenvoegen tot één totaaloverzicht...")
df_totaal = pd.concat(dfs_per_land.values(), axis=0).sort_index()
print(f"Totaaldataframe: {len(df_totaal)} rijen, {len(df_totaal.columns)} kolommen.")
 
# "segment" is alleen uniek BINNEN een land (NL-segment 0 ≠ BE-segment 0),
# daarom een aparte kolom met een landgebonden, globaal unieke segmentnaam:
df_totaal["segment_globaal"] = df_totaal['prd_country'] + "_" + df_totaal["segment"].astype(str)
print("Kolom 'segment_globaal' toegevoegd (land + segment, uniek over alle landen).")
 
df_totaal.to_csv("results/consumers_met_segmenten_per_land.csv", index=False)
print("consumers_met_segmenten_per_land.csv opgeslagen.")
 
# ---------------------------------------------------------------------------
# 5. INSPECTEREN
# ---------------------------------------------------------------------------
print("\n{20*'='} Overzicht segmentverdeling per land {20*'='}")
for land, df_land_resultaat in dfs_per_land.items():
    print(f"\n--- {land} ({len(df_land_resultaat)} rijen totaal) ---")
    print(df_land_resultaat["segment"].value_counts())
