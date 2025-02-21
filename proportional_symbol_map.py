import pandas as pd
from datetime import datetime, timedelta
import pydeck as pdk
import streamlit as st
import json
import logging

with open('proportional_symbol_map_documents_21Feb.json', 'r') as f:
    all_documents = json.load(f)

documents = []
for doc in all_documents:
    if 'districts' in doc and 'relevant_outcome_count' in doc:
        documents.append(doc)

df_districts = pd.read_excel('Updated_District_Mapping.xlsx')

st.session_state.visibility = "hidden"
st.session_state.disabled = False

time_dict = {
    '7 days': 7,
    '30 days': 30,
    '3 months': 90,
    '6 months': 180,
    '1 year': 365,
    'All time': 100000
}

#TODO: Change caseload phrase selection logic and include 7 days and 30 days time window
diseases_time_option = st.selectbox(
    'Time period: ', 
    (
        # '7 days', 
        # '30 days', 
        '3 months', 
        '6 months', 
        '1 year',
        'All time'
    ),
    label_visibility=st.session_state.visibility,
    disabled=st.session_state.disabled,
    key='diseases_time_option'
)

today = datetime.now()
time_period = today - timedelta(days=time_dict.get(diseases_time_option))

filtered_documents = []
for doc in documents:
    date_str = doc['date']
    if not isinstance(date_str, str):
        continue

    try:
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        if time_period <= date_obj <= today:
            filtered_documents.append(doc)
    except Exception as ex:
            logging.error(f"Error in disease_documents: {ex}")

st.write(f"Total results: {len(filtered_documents)}")

data = []
diseases = set()
outcome_counts = []
for idx, doc in enumerate(filtered_documents):
    if 'relevant_outcome_count' not in doc or 'matched_disease' not in doc:
        continue
    if 'caseload_phrases' not in doc:
        documents[idx]['caseload_phrases'] = 'No data available'
    if 'districts' in doc:
        for district in doc['districts']:
            if district in df_districts['district'].values:
                doc['district_latitude'] = df_districts[df_districts['district'] == district]['y'].values[0]
                doc['district_longitude'] = df_districts[df_districts['district'] == district]['x'].values[0]
                break

    if 'district_latitude' in doc and 'district_longitude' in doc and doc['relevant_outcome_count'] is not None:
        outcome_counts.append(doc['relevant_outcome_count'])
        data.append({
            'date': doc['date'],
            'latitude': doc['district_latitude'],
            'longitude': doc['district_longitude'],
            'districts': doc['districts'],
            'relevant_outcome_count': doc['relevant_outcome_count'],
            'caseload_phrases': doc['caseload_phrases'],
            'matched_disease': doc['matched_disease'],
            'coordinates': [doc['district_longitude'], doc['district_latitude']],
            'radius': doc['relevant_outcome_count'] / 100
        })
        diseases.update(doc['matched_disease'])

df = pd.DataFrame(data)

if len(outcome_counts) == 0:
    st.write("No data to display.")
    st.stop()

min_count = min(outcome_counts)
max_count = max(outcome_counts)

df['normalized_outcome_count'] = df['relevant_outcome_count'].apply(
    lambda x: (x - min_count) / (max_count - min_count) if max_count != min_count else 0
)

df['radius'] = df['normalized_outcome_count'] * 100000

selected_diseases = st.multiselect(
    'Select Disease(s) to Display on the Map',
    list(diseases),
    default=['dengue'],
)

if st.radio("Select All Diseases", ['Yes', 'No'], index=1) == 'Yes':
    selected_diseases = list(diseases)

if selected_diseases:
    filtered_df = df[df['matched_disease'].apply(lambda x: any(disease in selected_diseases for disease in x))]
else:
    filtered_df = pd.DataFrame() 

filtered_df.reset_index(drop=True, inplace=True)

#to show only the most recent outbreaks
# if not filtered_df.empty:
#     filtered_df = filtered_df.sort_values('date', ascending=False)
#     filtered_df = filtered_df.drop_duplicates(subset=['latitude', 'longitude'], keep='first')

if not filtered_df.empty:
    max_count = filtered_df['relevant_outcome_count'].max()
    min_count = filtered_df['relevant_outcome_count'].min()
    if max_count > min_count:  # Avoid division by zero
        filtered_df['radius'] = ((filtered_df['relevant_outcome_count'] - min_count) / (max_count - min_count)) * 50000000 + 5
    else:
        filtered_df['radius'] = 1000  # Default small size if all values are the same

    layer = pdk.Layer(
        "ScatterplotLayer",
        filtered_df,
        pickable=True,
        opacity=0.2,
        stroked=True,
        filled=True,
        radius_scale=1,
        radius_min_pixels=1,
        radius_max_pixels=30,
        line_width_min_pixels=1,
        get_position="coordinates",
        get_radius="radius",
        get_fill_color=[245, 221, 66],
        get_line_color=[0, 0, 0],
        get_tooltip="caseload_phrases"
    )

    view_state = pdk.ViewState(
        latitude=20.5937,
        longitude=78.9629,
        zoom=4,
        bearing=0,
        pitch=0
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))

st.write("### Filtered Data for Selected Diseases")
if not filtered_df.empty:
    st.dataframe(filtered_df[['districts', 'relevant_outcome_count', 'caseload_phrases']])
else:
    st.write("No data available for the selected diseases.")