"""Vivacity API client for fetching traffic sensor data.

The Vivacity API provides traffic counts from AI-powered sensors.
API keys are region-specific (e.g., WYCA for West Yorkshire).

API Documentation: https://docs.vivacitylabs.com/
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import httpx
import pandas as pd

from .constants import VIVACITY_TO_UNIFIED

# Vivacity class names mapped to unified modes
VIVACITY_CLASS_MAP = VIVACITY_TO_UNIFIED


def batch_date_range(from_date: datetime, to_date: datetime, max_days: int = 7) -> list[dict]:
    """Split a date range into batches of max_days.
    
    Vivacity API limits requests to 7 days at a time.
    """
    batches = []
    current = from_date
    while current < to_date:
        batch_end = min(current + timedelta(days=max_days), to_date)
        batches.append({"from": current, "to": batch_end})
        current = batch_end
    return batches


class VivacityClient:
    """Async client for the Vivacity traffic sensor API."""

    def __init__(
        self,
        region_code: str,
        api_key: Optional[str] = None,
        base_url: str = "https://api.vivacitylabs.com",
        timeout: float = 120.0,
    ):
        """Initialize Vivacity client for a specific region.
        
        Args:
            region_code: Region code (e.g., 'wyca' for West Yorkshire)
            api_key: Optional API key override. If not provided, looks for VIVACITY_{REGION} env var.
            base_url: API base URL
            timeout: Request timeout in seconds
        """
        self.region_code = region_code.lower()
        self.api_key = api_key or os.getenv(f"VIVACITY_{region_code.upper()}")
        
        if not self.api_key:
             available = [k for k in os.environ if k.startswith("VIVACITY_") and k not in ("VIVACITY_BASE_URL", "VIVACITY_TIMEOUT")]
             raise ValueError(
                f"No Vivacity API key configured for region '{region_code}'. "
                f"Set VIVACITY_{region_code.upper()} environment variable. "
                f"Available env vars: {', '.join(available)}"
            )

        self.base_url = base_url
        self.timeout = timeout
        self.headers = {
            "x-vivacity-api-key": self.api_key,
            "User-Agent": "VivacityPy/1.0",
        }
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "VivacityClient":
        self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("VivacityClient must be used as async context manager")
        return self._client

    async def get_countline_metadata(self) -> list[dict]:
        """Fetch all countline metadata for this region.
        
        Returns list of dicts with:
        - id: Countline ID
        - name: Countline name
        - sensor_name: Simplified sensor name
        - geometry: GeoJSON LineString geometry
        - is_speed: Whether speed data is available
        """
        resp = await self.client.get(f"{self.base_url}/countline/metadata")
        resp.raise_for_status()
        
        data = resp.json()
        countlines = []
        
        for countline_id, item in data.items():
            # Extract geometry
            geometry = None
            if item.get("geometry") and item["geometry"].get("geo_json"):
                geo_json = item["geometry"]["geo_json"]
                if geo_json.get("coordinates"):
                    geometry = {
                        "type": "LineString",
                        "coordinates": geo_json["coordinates"]
                    }
            
            # Simplify name (extract sensor ID and first location part)
            name = item.get("name", "")
            parts = name.split("_")
            sensor_name = "_".join(parts[:2]) if len(parts) >= 2 else name
            
            countlines.append({
                "id": countline_id,
                "name": name,
                "sensor_name": sensor_name,
                "description": item.get("description", ""),
                "is_speed": item.get("is_speed", False),
                "geometry": geometry,
                "hardware_id": item.get("hardware_id"),
                "viewpoint_id": item.get("viewpoint_id"),
            })
        
        return countlines

    async def get_hardware_metadata(self) -> list[dict]:
        """Fetch hardware (sensor) metadata with locations.
        
        Returns list of dicts with:
        - id: Hardware ID
        - name: Hardware name
        - lat: Latitude
        - lon: Longitude (from 'long' field in API)
        - project_name: Project name
        - hardware_version: Version
        """
        resp = await self.client.get(f"{self.base_url}/hardware/metadata")
        resp.raise_for_status()
        
        data = resp.json()
        hardware = []
        
        for hw_id, item in data.items():
            hardware.append({
                "id": hw_id,
                "name": item.get("name"),
                "lat": item.get("lat"),
                "lon": item.get("long"),  # API uses 'long'
                "project_name": item.get("project_name"),
                "hardware_version": item.get("hardware_version"),
            })
        
        return hardware

    async def get_counts(
        self,
        countline_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        time_bucket: str = "1h",
        bidirectional: bool = True,
    ) -> list[dict]:
        """Fetch counts for countlines within a time range.
        
        Args:
            countline_ids: List of countline IDs to query
            start_time: Start of time range
            end_time: End of time range
            time_bucket: Aggregation bucket (e.g., "1h", "24h")
            bidirectional: If True, sums clockwise and anti_clockwise counts.
                           If False, preserves direction in output.
            
        Returns:
            List of count records.
        """
        # Vivacity API limits to 7 days per request
        date_batches = batch_date_range(start_time, end_time, max_days=7)
        
        # Also batch countline_ids to avoid too long URLs and timeouts
        id_batches = [countline_ids[i:i + 50] for i in range(0, len(countline_ids), 50)]
        
        all_records = []
        
        for id_batch in id_batches:
            for date_batch in date_batches:
                params = {
                    "countline_ids": ",".join(id_batch),
                    "from": date_batch["from"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": date_batch["to"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "time_bucket": time_bucket,
                }
                
                try:
                    resp = await self.client.get(
                        f"{self.base_url}/countline/counts",
                        params=params
                    )
                    
                    if resp.status_code != 200:
                        continue
                        
                    data = resp.json()
                    
                    # Parse response - structure is {countline_id: [records]}
                    for countline_id, records in data.items():
                        if not records:
                            continue
                            
                        for record in records:
                            from_time = record.get("from")
                            to_time = record.get("to")
                            
                            # Process each direction
                            for direction in ["clockwise", "anti_clockwise"]:
                                dir_data = record.get(direction, {})
                                if not dir_data:
                                    continue
                                    
                                # Extract counts by class
                                for viv_class, count in dir_data.items():
                                    if viv_class == "total" or count is None:
                                        continue
                                        
                                    # Map to standard mode
                                    mode = VIVACITY_CLASS_MAP.get(viv_class, viv_class)
                                    
                                    all_records.append({
                                        "countline_id": countline_id,
                                        "timestamp": from_time,
                                        "from": from_time,
                                        "to": to_time,
                                        "direction": direction,
                                        "class": viv_class,
                                        "mode": mode,
                                        "count": count,
                                    })
                except Exception as e:
                    print(f"Error fetching counts for batch: {e}")
                    continue
        
        if bidirectional:
            # Aggregate to sum directions
            df = pd.DataFrame(all_records)
            if df.empty:
                return []
            
            # Group by everything except direction and count, then sum count
            df_agg = df.groupby(["countline_id", "timestamp", "from", "to", "class", "mode"]).agg({
                "count": "sum"
            }).reset_index()
            return df_agg.to_dict(orient="records")
            
        return all_records

    async def get_speed(
        self,
        countline_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        time_bucket: str = "24h",
    ) -> list[dict]:
        """Fetch speed data for countlines.
        
        Args:
            countline_ids: List of countline IDs to query
            start_time: Start of time range
            end_time: End of time range
            time_bucket: Aggregation bucket
            
        Returns:
            List of speed records with percentile data
        """
        # Vivacity API limits to 7 days per request
        date_batches = batch_date_range(start_time, end_time, max_days=7)
        
        # Batch countline_ids
        id_batches = [countline_ids[i:i + 50] for i in range(0, len(countline_ids), 50)]
        
        all_records = []
        
        for id_batch in id_batches:
            for date_batch in date_batches:
                params = {
                    "countline_ids": ",".join(id_batch),
                    "from": date_batch["from"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "to": date_batch["to"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "time_bucket": time_bucket,
                }
                
                try:
                    resp = await self.client.get(
                        f"{self.base_url}/countline/speed",
                        params=params
                    )
                    
                    if resp.status_code != 200:
                        continue
                        
                    data = resp.json()
                    
                    for countline_id, records in data.items():
                        if not records:
                            continue
                            
                        for record in records:
                            all_records.append({
                                "countline_id": countline_id,
                                "from": record.get("from"),
                                "to": record.get("to"),
                                "mean_speed": record.get("mean"),
                                "p50_speed": record.get("p50"),
                                "p85_speed": record.get("p85"),
                                "sample_size": record.get("sample_size"),
                            })
                except Exception as e:
                    print(f"Error fetching speed for batch: {e}")
                    continue
        
        return all_records

    async def fetch_region_traffic(
        self,
        countline_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        region_name: str,
        time_bucket: str = "1h",
        bidirectional: bool = True,
    ) -> pd.DataFrame:
        """Fetch traffic data for countlines and format for database ingestion.
        
        Args:
            countline_ids: List of countline IDs
            start_time: Start of time range
            end_time: End of time range
            region_name: Name of the region for tagging
            time_bucket: Aggregation bucket
            bidirectional: If True, sums directions. If False, preserves 'direction' column.
            
        Returns:
            DataFrame ready for ingestion.
        """
        # Fetch counts
        counts = await self.get_counts(
            countline_ids, start_time, end_time, time_bucket, bidirectional=bidirectional
        )
        
        if not counts:
            return pd.DataFrame()
        
        # Convert to DataFrame
        df = pd.DataFrame(counts)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.rename(columns={"countline_id": "sensor_id"})
        df["region"] = region_name
        df["source"] = "vivacity"
        
        if bidirectional:
             # Standard format for counterflow.daily_counts compatibility
             df["v85"] = None
             return df[["timestamp", "sensor_id", "mode", "count", "v85", "region", "source"]]
        
        # Preservation of direction for vivacity_traffic_counts
        return df[["timestamp", "sensor_id", "direction", "mode", "count", "region", "source"]]

    async def fetch_region_traffic_with_speed(
        self,
        countline_ids: list[str],
        start_time: datetime,
        end_time: datetime,
        region_name: str,
        time_bucket: str = "1h",
    ) -> pd.DataFrame:
        """Fetch traffic data with speed information.
        
        Similar to fetch_region_traffic but also fetches speed data
        and joins it to car mode records.
        """
        # Fetch counts
        df = await self.fetch_region_traffic(
            countline_ids, start_time, end_time, region_name, time_bucket
        )
        
        if df.empty:
            return df
        
        # Fetch speed data (daily aggregation for efficiency)
        speed_records = await self.get_speed(
            countline_ids, start_time, end_time, time_bucket="24h"
        )
        
        if speed_records:
            speed_df = pd.DataFrame(speed_records)
            speed_df["date"] = pd.to_datetime(speed_df["from"]).dt.date
            speed_df = speed_df.rename(columns={"countline_id": "sensor_id"})
            
            # Average speed per sensor per day
            speed_daily = speed_df.groupby(["sensor_id", "date"]).agg({
                "p85_speed": "mean"
            }).reset_index()
            
            # Add date column to main df for joining
            df["date"] = df["timestamp"].dt.date
            
            # Join speed to car records
            df = df.merge(
                speed_daily[["sensor_id", "date", "p85_speed"]],
                on=["sensor_id", "date"],
                how="left"
            )
            
            # Only apply v85 to car mode
            df.loc[df["mode"] == "car", "v85"] = df.loc[df["mode"] == "car", "p85_speed"]
            df = df.drop(columns=["date", "p85_speed"])
        
        return df
