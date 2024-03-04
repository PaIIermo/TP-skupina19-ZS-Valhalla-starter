import pandas as pd
import requests as rq
import json
import folium
from io import StringIO

original_df = pd.read_csv("dataset.csv")
desired_columns = ['latitude', 'longtitude']  #'id', 'sensor_time', 
df = original_df[desired_columns]

sample = df.iloc[:10].copy()
sample.columns = ['lat', 'lon'] #'id', 'time', 
#sample['time'] = pd.to_datetime(sample['time'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')

sample['lat'] = sample['lat'].round(6)
sample['lon'] = sample['lon'].round(6)

# First and last points in a isolated trip have type break, others via
# (documentation for more detailed explanation)
sample['type'] = 'via'
sample.at[0, 'type'] = 'break'
sample.at[len(sample) - 1, 'type'] = 'break'

# Request creation
meili_coordinates = sample.to_json(orient='records')

meili_head = '{"shape":'
meili_tail = ""","search_radius": 250, "shape_match":"map_snap", "costing":"auto", "format":"osrm"}"""

meili_request_body = meili_head + meili_coordinates + meili_tail

# http://valhalla:8002/trace_route
url = "http://localhost:8002/trace_route"
headers = {'Content-type': 'application/json'}
data = str(meili_request_body)

# Request is sent
r = rq.post(url, data=data, headers=headers)

if r.status_code == 200:
    # Parsing the JSON response
    response_text = json.loads(r.text)
    resp = str(response_text['tracepoints'])
    
    # This is a replacement to distinguish single None's in a row
    # from "waypoint_index" being None
    resp = resp.replace("'waypoint_index': None", "'waypoint_index': '#'")
    resp = resp.replace("None", "{'matchings_index': '#', 'name': '', 'waypoint_index': '#', 'alternatives_count': 0, 'distance': 0, 'location': [0.0, 0.0]}")
    
    # This is to make it a valid JSON
    resp = resp.replace("'", '"')
    resp = json.dumps(resp)
    resp = json.loads(resp)
    
    # Saving the columns we need
    df_response = pd.read_json(StringIO(resp))
    df_response = df_response[['name', 'distance', 'location']]

    # Merging our initial data with the response from Meili by index
    df_optimized = pd.merge(sample, df_response, left_index=True, right_index=True)
    df_optimized['map_matched_lat'] = df_optimized['location'].apply(lambda x: x[1])
    df_optimized['map_matched_lon'] = df_optimized['location'].apply(lambda x: x[0])

    df_optimized.drop('location', axis=1, inplace=True)

    # Reorder the DataFrame to place the map-matched lat and lon directly to the right of the original coordinates
    columns_order = ['lat', 'lon', 'map_matched_lat', 'map_matched_lon', 'type', 'name', 'distance']
    df_optimized = df_optimized[columns_order]
    
    print(df_optimized)

    m = folium.Map(location=[df_optimized['lat'].mean(), df_optimized['lon'].mean()], zoom_start=13)

    # Add points for the original coordinates
    for idx, row in df_optimized.iterrows():
        folium.CircleMarker([row['lat'], row['lon']], radius=3, color='blue', fill=True, fill_color='blue', fill_opacity=0.7, popup=row['name']).add_to(m)

    # Add points for the map-matched coordinates
    for idx, row in df_optimized.iterrows():
        folium.CircleMarker([row['map_matched_lat'], row['map_matched_lon']], radius=3, color='red', fill=True, fill_color='red', fill_opacity=0.7, popup=row['name']).add_to(m)

    m.save('visual.html')