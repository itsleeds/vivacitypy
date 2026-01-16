import re

def format_road_name(camel_case: str) -> str:
    """Convert CamelCase road name to properly spaced and capitalized format.
    
    Examples:
        'StCeciliaSt' -> 'St Cecilia Street'
        'WoodhouseLn' -> 'Woodhouse Lane'
        'vicarLn' -> 'Vicar Lane'
        'parkRow' -> 'Park Row'
        'HunsletRd' -> 'Hunslet Road'
    
    Args:
        camel_case: CamelCase road name from Vivacity sensor name
        
    Returns:
        Properly formatted road name with spaces and correct capitalization
    """
    if not camel_case:
        return camel_case
    
    # Insert spaces before capital letters (but not at start)
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', camel_case)
    
    # Also handle lowercase to uppercase transitions after numbers
    result = re.sub(r'(\d)([A-Z])', r'\1 \2', result)
    
    # Split into words for processing
    words = result.split()
    
    # Only expand abbreviations at the END of the name (last word)
    # Common road type abbreviations
    road_type_abbrevs = {
        'st': 'Street',
        'ln': 'Lane',
        'rd': 'Road',
        'ave': 'Avenue',
        'dr': 'Drive',
        'ct': 'Court',
        'pl': 'Place',
        'cres': 'Crescent',
        'cr': 'Crescent',
        'gr': 'Grove',
        'pk': 'Park',
        'sq': 'Square',
        'terr': 'Terrace',
        'jnt': 'Junction',
        'way': 'Way',
    }
    
    if words:
        last_word = words[-1].lower()
        if last_word in road_type_abbrevs:
            words[-1] = road_type_abbrevs[last_word]
    
    # Title case each word
    result = ' '.join(word.capitalize() for word in words)
    
    return result


def extract_camera_id(sensor_name: str) -> tuple[str, str, str, str]:
    """Extract camera_id, cordon_name, road_name, and counter_type from Vivacity sensor name.
    
    Groups ALL sensors from the same camera installation into a single camera_id.
    The camera prefix (S40, S41, etc.) combined with the road/location name 
    defines the camera - path types (LHS/RHS), crossing types, etc. are sub-cordons
    and should NOT create separate camera entries.
    
    e.g. 'S40_WoodhouseLn_road_wyca001' -> ('S40_woodhouseln', 'S40', 'WoodhouseLn', 'segment')
         'S40_WoodhouseLn_pathLHS_wyca001' -> ('S40_woodhouseln', 'S40', 'WoodhouseLn', 'segment')
         'S40_Vicarln_crossing_south_lptip001' -> ('S40_vicarl', 'S40', 'Vicarln', 'crossing')
    
    Returns:
        (camera_id, cordon_name, road_name, counter_type) tuple
    """
    if not sensor_name:
        return (None, None, None, None)
    
    name_lower = sensor_name.lower()
    
    # 1. Determine counter_type from the sensor name
    # Crossings are pedestrian/cycle crossings at junctions
    # Segments are along-road counts (road, path, cyclepath, etc.)
    if '_crossing' in name_lower:
        counter_type = 'crossing'
    elif any(x in name_lower for x in ['_road', '_path', '_cyclepath', '_cyclelane', '_buslan']):
        counter_type = 'segment'
    else:
        counter_type = 'unknown'
    
    # 2. Extract camera prefix (e.g. S31_, S40_)
    # This prefix uniquely identifies the camera installation
    parts = sensor_name.split('_', 1)
    if len(parts) == 2 and re.match(r'^[Ss]\d+$', parts[0]):
        cordon_name = parts[0].upper()
        name_body = parts[1]
    else:
        cordon_name = None
        name_body = sensor_name
    
    # 3. Extract road name (first part after camera prefix, before type indicators)
    # Pattern: RoadName_type_region or RoadName_typeDirection_region
    body_parts = name_body.split('_')
    if body_parts:
        raw_road_name = body_parts[0]  # Keep original case for processing
        road_name = format_road_name(raw_road_name)  # Convert to proper format
    else:
        road_name = None
        raw_road_name = None
        
    # 4. Create normalized location_id for grouping
    location_id = raw_road_name.lower() if raw_road_name else ''
    
    # Strip trailing compass directions from location_id (e.g., HunsletRdS -> hunsletrd)
    location_id = re.sub(r'[nsew]$', '', location_id)
    
    # 5. Combine camera prefix with location to create unique camera_id
    # All cordons from the same camera (e.g., S40_WoodhouseLn_road, S40_WoodhouseLn_pathLHS)
    # will share the same camera_id
    if cordon_name:
        camera_id = f"{cordon_name}_{location_id}"
    else:
        camera_id = location_id
    
    return (camera_id, cordon_name, road_name, counter_type)
