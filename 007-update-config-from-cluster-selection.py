def run():
    import os
    import glob
    import re
    import pandas as pd
    import json

    # Specify the directory
    directory = './results/'  # Use your directory path here

    # Find all cluster_selection_*.csv files. Filenames look like
    # cluster_selection_feat12_2026-08-18_09-04.csv (see config.py's
    # FEATURE_TAG) - group by the feat<N> tag so each feature-count sweep
    # gets its own config file instead of the newest one clobbering the rest.
    files = glob.glob(os.path.join(directory, 'cluster_selection_*.csv'))

    if not files:
        print(f"No cluster_selection_*.csv files found in {directory} - nothing to do.")
        return

    tag_pattern = re.compile(r'cluster_selection_(feat\d+)_')
    files_by_tag = {}
    for f in files:
        match = tag_pattern.search(os.path.basename(f))
        tag = match.group(1) if match else "untagged"
        files_by_tag.setdefault(tag, []).append(f)

    written_files = []

    for tag in sorted(files_by_tag):
        tag_files = files_by_tag[tag]

        # Get the newest file for this tag by modification time
        newest_file = max(tag_files, key=os.path.getmtime)

        df = pd.read_csv(newest_file)
        print(f"[{tag}] Loaded: {newest_file}")

        # Drop rows where 'land' is empty or NaN
        df = df.dropna(subset=['land'])

        # bic/aic columns are only present if the underlying GMM exposed
        # lower_bound_ (see 005-cluster-selection-pipeline.py) - guard
        # against them being absent entirely.
        if 'bic' in df.columns:
            df['bic'] = df['bic'].fillna(float('inf'))
        if 'aic' in df.columns:
            df['aic'] = df['aic'].fillna(float('inf'))

        # Sort by land, then by silhouette_score (desc), davies_bouldin_score (asc)
        df = df.sort_values(
            by=['land', 'silhouette_score', 'davies_bouldin_score'],
            ascending=[True, False, True]
        )

        # For each country, keep only the first row (best by silhouette, then davies_bouldin_score)
        best_per_country = df.drop_duplicates(subset='land', keep='first')

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

        # Save to a tagged JSON file so each feature-count run keeps its own
        # config instead of overwriting the others. config.py loads
        # gmm_n_components_<FEATURE_TAG>.json automatically based on the
        # active FEATURE_SET env var.
        out_filename = "gmm_n_components.json" if tag == "untagged" else f"gmm_n_components_{tag}.json"
        with open(out_filename, 'w') as f:
            json.dump(formatted_config, f, indent=4)

        print(f"[{tag}] Saved configuration per country to '{out_filename}':")
        print(json.dumps(formatted_config, indent=4))
        written_files.append(out_filename)

    print(f"\nWrote {len(written_files)} config file(s): {', '.join(written_files)}")


if __name__ == "__main__":
    run()
