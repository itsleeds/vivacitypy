# vivacitypy

A Python client for the [Vivacity Labs](https://vivacitylabs.com/) Traffic Data API.

## Installation

```bash
pip install git+https://github.com/itsleeds/vivacitypy.git
```

## Usage

```python
import asyncio
from vivacitypy import VivacityClient

async def main():
    async with VivacityClient(region_code="wyca") as client:
        # Get sensor metadata
        sensors = await client.get_countline_metadata()
        print(f"Found {len(sensors)} sensors")

if __name__ == "__main__":
    asyncio.run(main())
```

## Environment Variables

The client expects your API key to be stored in an environment variable named `VIVACITY_{REGION_CODE}` (e.g., `VIVACITY_WYCA`).
Alternatively, you can pass the `api_key` directly to the constructor.
