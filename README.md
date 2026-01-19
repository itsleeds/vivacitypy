# vivacitypy

A Python client for the [Vivacity Labs](https://vivacitylabs.com/) Traffic Data API.

## Installation

```bash
pip install git+https://github.com/itsleeds/vivacitypy.git
```

## Usage

### Basic Usage

```python
import asyncio
from vivacitypy import VivacityClient

async def main():
    async with VivacityClient(region_code="anytown") as client:
        # Get countline metadata
        countlines = await client.get_countline_metadata()
        
        # Get hardware (camera) metadata
        hardware = await client.get_hardware_metadata()

if __name__ == "__main__":
    asyncio.run(main())
```

### Metadata Examples

#### 1. Hardware (Camera) Metadata
Returns physical location and device info.

```python
hardware = await client.get_hardware_metadata()
```

**Output Structure:**
```json
[
  {
    "id": "1001",
    "name": "Camera-North",
    "lat": 51.5074,
    "lon": -0.1278,
    "project_name": "anytown-smartcity",
    "hardware_version": "v2"
  }
]
```

#### 2. Countline (Cordon) Metadata
Returns logical countlines and their association with hardware.

```python
countlines = await client.get_countline_metadata()
```

**Output Structure:**
```json
[
  {
    "id": "55001",
    "name": "S1_AnyStreet_Northbound",
    "sensor_name": "S1_AnyStreet",
    "description": "Main road northbound",
    "is_speed": true,
    "geometry": {
      "type": "LineString",
      "coordinates": [[-0.1278, 51.5074], [-0.1279, 51.5075]]
    },
    "hardware_id": "1001",
    "viewpoint_id": "2001"
  }
]
```

### Fetching Traffic Data

#### 1. Summed Data (Default)
Useful for general analysis and compatibility with legacy tools.

```python
df = await client.fetch_region_traffic(
    sensor_ids=["99001"], 
    start_time=start, 
    end_time=end, 
    region_name="anytown",
    bidirectional=True  # Default
)
```

**Output Structure:**
| timestamp | sensor_id | mode | count | v85 | region | source |
|-----------|-----------|------|-------|-----|--------|--------|
| 2026-01-01 12:00:00 | 99001 | car | 45 | None | anytown | vivacity |
| 2026-01-01 12:00:00 | 99001 | bike | 7 | None | anytown | vivacity |
| 2026-01-01 13:00:00 | 99001 | car | 38 | None | anytown | vivacity |

#### 2. Directional Data
Retrieves raw counts for each direction independently.

```python
df = await client.fetch_region_traffic(
    sensor_ids=["99001"], 
    start_time=start, 
    end_time=end, 
    region_name="anytown",
    bidirectional=False
)
```

**Output Structure:**
| timestamp | sensor_id | direction | mode | count | region | source |
|-----------|-----------|-----------|------|-------|--------|--------|
| 2026-01-01 12:00:00 | 99001 | clockwise | car | 20 | anytown | vivacity |
| 2026-01-01 12:00:00 | 99001 | anti_clockwise | car | 25 | anytown | vivacity |
| 2026-01-01 12:00:00 | 99001 | clockwise | bike | 3 | anytown | vivacity |

## Environment Variables

The client expects your API key to be stored in an environment variable named `VIVACITY_{REGION_CODE}` (e.g., `VIVACITY_ANYTOWN`).
Alternatively, you can pass the `api_key` directly to the constructor.
