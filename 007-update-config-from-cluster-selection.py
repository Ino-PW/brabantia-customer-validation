def run():
    import os
    import glob
    import pandas as pd
    import json

    # Specify the directory
    directory = './results/'  # Use your directory path here

    # Find all files starting with 'cluster_selection_'
    files = glob.glob(os.path.join(directory, 'cluster_selection_*'))

    # Get the newest file by modification time
    newest_file = max(files, key=os.path.getmtime)

    # Load the file (example: read as text)
    with open(newest_file, 'r') as f:
        content = f.read()
        df = pd.read_csv(newest_file)  # Load the CSV into a DataFrame

    print(f"Loaded: {newest_file}")

    # Drop rows where 'land' is empty or NaN
    df = df.dropna(subset=['land'])

    df['bic'] = df['bic'].fillna(float('inf'))
    df['aic'] = df['aic'].fillna(float('inf'))

    # Sort the entire DataFrame by land, then by silhouette_score (desc), davies_bouldin_score (asc)
    df = df.sort_values(
        by=['land', 'silhouette_score', 'davies_bouldin_score'],
        ascending=[True, False, True]
    )

    # For each country, keep only the first row (best by silhouette, then davies_bouldin_score)
    best_per_country = df.drop_duplicates(subset='land', keep='first')

    # Select relevant columns for output
    result = best_per_country[
        ['type', 'n_clusters', 'silhouette_score', 'davies_bouldin_score',
        'calinski_harabasz_score', 'best_init_setup', 'bic', 'aic', 'land']
    ]


    # Extract the country, n_clusters, best_init_setup, and covariance type (type) as a dictionary
    config_update = best_per_country.set_index('land')[['n_clusters', 'best_init_setup', 'type']].to_dict(orient='index')

    # Convert values to native Python types (int, str)
    formatted_config = {
        country: {
            "n_clusters": int(data["n_clusters"]),
            "best_init_setup": int(data["best_init_setup"]),
            "covariance_type": data["type"]
        }
        for country, data in config_update.items()
    }

    # Save to a JSON file for config.py to read
    with open('gmm_n_components.json', 'w') as f:
        json.dump(formatted_config, f, indent=4)

    print("\nSaved configuration per country to 'gmm_n_components.json':")
    print(json.dumps(formatted_config, indent=4))

if __name__ == "__main__":
    run()