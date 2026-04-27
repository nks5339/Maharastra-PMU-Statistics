from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

DATASET_CONFIG = {
    "specialisation": {
        "filename": "specialisation_index.csv",
        "value_col": "specialisation_index",
        "label": "Specialisation Index",
        "color": "#33c3ff",
    },
    "combined": {
        "filename": "combined_index.csv",
        "value_col": "combined_index",
        "label": "Combined Index",
        "color": "#a78bfa",
    },
    "productivity": {
        "filename": "productivity_index.csv",
        "value_col": "productivity_index",
        "label": "Productivity Index",
        "color": "#f59e0b",
    },
}

app = FastAPI(title="Maharashtra District Intelligence", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def normalize_name(value: str) -> str:
    return str(value).strip().lower()


def validate_dataframe(df: pd.DataFrame, dataset_type: str) -> pd.DataFrame:
    config = DATASET_CONFIG[dataset_type]
    required = {
        "District",
        "district_name",
        config["value_col"],
        "nic3_code",
        "nic3_name",
        "rank",
    }
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Missing columns in {config['filename']}: {sorted(missing)}",
        )
    return df


@lru_cache(maxsize=8)
def load_dataset_cached(dataset_type: str, mtime: float) -> pd.DataFrame:
    config = DATASET_CONFIG[dataset_type]
    path = DATA_DIR / config["filename"]
    df = pd.read_csv(path)
    return validate_dataframe(df, dataset_type)


def load_dataset(dataset_type: str) -> pd.DataFrame:
    config = DATASET_CONFIG.get(dataset_type)
    if not config:
        raise HTTPException(status_code=400, detail="Invalid dataset type")

    path = DATA_DIR / config["filename"]
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Dataset file not found: {config['filename']}",
        )

    return load_dataset_cached(dataset_type, path.stat().st_mtime)


def get_district_lookup() -> List[Dict]:
    df = load_dataset("specialisation")
    districts = (
        df[["District", "district_name"]]
        .drop_duplicates()
        .sort_values(["district_name", "District"])
    )

    rows = []
    for _, row in districts.iterrows():
        rows.append(
            {
                "district_code": int(row["District"]),
                "district_name": str(row["district_name"]),
                "district_key": normalize_name(row["district_name"]),
            }
        )
    return rows


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )



@app.get("/api/health")
def health():
    files = {
        k: (DATA_DIR / v["filename"]).exists()
        for k, v in DATASET_CONFIG.items()
    }
    return {
        "status": "ok",
        "data_dir": str(DATA_DIR),
        "files": files,
    }


@app.get("/api/config")
def config():
    return {
        "datasets": {
            key: {
                "label": value["label"],
                "color": value["color"],
                "filename": value["filename"],
            }
            for key, value in DATASET_CONFIG.items()
        }
    }


@app.get("/api/districts")
def districts():
    return {"districts": get_district_lookup()}


@app.get("/api/district-code")
def district_code(district_name: str = Query(..., min_length=1)):
    lookup = {item["district_key"]: item for item in get_district_lookup()}
    key = normalize_name(district_name)
    item = lookup.get(key)

    if not item:
        raise HTTPException(
            status_code=404,
            detail=f"District not found: {district_name}",
        )

    return item


@app.get("/api/district-data")
def district_data(
    dataset_type: str = Query(..., pattern="^(specialisation|combined|productivity)$"),
    district_name: Optional[str] = None,
    district_code: Optional[int] = None,
):
    if district_name is None and district_code is None:
        raise HTTPException(
            status_code=400,
            detail="Provide district_name or district_code",
        )

    df = load_dataset(dataset_type)
    config = DATASET_CONFIG[dataset_type]
    value_col = config["value_col"]

    if district_code is not None:
        filtered = df[df["District"].astype(int) == int(district_code)]
    else:
        filtered = df[
            df["district_name"].astype(str).str.strip().str.lower()
            == normalize_name(district_name)
        ]

    if filtered.empty:
        raise HTTPException(
            status_code=404,
            detail="No data found for the requested district",
        )

    filtered = filtered.sort_values("rank").head(10)

    district_code_value = int(filtered.iloc[0]["District"])
    district_name_value = str(filtered.iloc[0]["district_name"])

    rows = []
    for _, row in filtered.iterrows():
        rows.append(
            {
                "rank": int(row["rank"]),
                "nic3_code": int(row["nic3_code"]),
                "nic3_name": str(row["nic3_name"]),
                "value": float(row[value_col]),
            }
        )

    return {
        "district_code": district_code_value,
        "district_name": district_name_value,
        "dataset_type": dataset_type,
        "dataset_label": config["label"],
        "color": config["color"],
        "top_10": rows,
    }