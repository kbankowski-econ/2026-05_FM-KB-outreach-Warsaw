import os
import warnings

import pandas as pd
from imf_datatools import idata_utilities

idata_utilities.PRIVATE = True

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
OUTPUT_PATH = os.path.join(BASE_DIR, 'data/fmData/global_real_gdp_growth.csv')

VINTAGES = {
    'ngdp_rpch_2026apr': 'IMF.RES.WEO:WEO_LIVE_2026_APR_VINTAGE',
    'ngdp_rpch_2025apr': 'IMF.RES.WEO:WEO_LIVE_2025_APR_VINTAGE',
}
KEY = 'G001.NGDP_RPCH.A'


def fetch_vintage(db, key, value_col):
    print(f"Fetching {db} ({key})...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df = idata_utilities.get_idata_data(db, key=key, longformat=True)

    if df is None or df.empty:
        print(f"  No data returned for {db}.")
        return None

    col_map = {}
    for c in df.columns:
        low = c.lower()
        if any(x in low for x in ['time', 'year', 'date']):
            col_map[c] = 'year'
        elif any(x in low for x in ['value', 'obs_value']):
            col_map[c] = value_col

    df = df.rename(columns=col_map)[['year', value_col]]

    if df['year'].dtype == 'O':
        df['year'] = pd.to_datetime(df['year'], errors='coerce').dt.year
    elif pd.api.types.is_datetime64_any_dtype(df['year']):
        df['year'] = df['year'].dt.year

    return df.dropna(subset=['year', value_col]).astype({'year': int}).sort_values('year')


def main():
    frames = []
    for value_col, db in VINTAGES.items():
        df = fetch_vintage(db, KEY, value_col)
        if df is not None:
            frames.append(df)

    if not frames:
        print("Error: No data returned from any vintage.")
        return

    out = frames[0]
    for df in frames[1:]:
        out = out.merge(df, on='year', how='outer')
    out = out.sort_values('year').reset_index(drop=True)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    out.to_csv(OUTPUT_PATH, index=False)
    print(f"Saved {len(out)} rows to {OUTPUT_PATH}")
    print(out.tail())


if __name__ == "__main__":
    main()
