# sf_rental_map.py
import re
import difflib
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output


# Initialize Dash app
app = dash.Dash(__name__)

DEFAULT_SEARCH_QUERY = "100 Larkin St"  # Replace with your desired default address

# App layout with search bar and map
app.layout = html.Div([
    dcc.Input(
        id="block_search",
        type="text",
        value="",  # Keep the input field visibly empty
        debounce=True,
        placeholder="Enter block and street name (ex. 100 Larkin St)",
        style={"margin-bottom": "20px", "width": "300px"}
    ),
    html.Div(id="output"),
    dcc.Graph(id="sf_map")
])

@app.callback(
    [Output("sf_map", "figure"),            # Output for the map
     Output("output", "children")], 
    [Input("block_search", "value")]
)
def update_map(search_query):
    print("Callback triggered")
    print(f"Search Query (raw): {search_query}")

    # If input is empty, fallback to the default search query
    if not search_query or search_query.strip() == "":
        print("Empty search query - using default query.")
        search_query = DEFAULT_SEARCH_QUERY

    search_query_cleaned = search_query.strip()
    print(f"Cleaned Search Query: {search_query_cleaned}")

    address_match = re.match(r'(\d+)?\s*(.+)', search_query_cleaned)
    if address_match:
        input_number = address_match.group(1)
        input_street = address_match.group(2).strip()

        if not input_street:
            print("Invalid query - missing street name.")
            # Return default map and error message
            return update_map_with_message(DEFAULT_SEARCH_QUERY, "Invalid input. Please enter a valid street name.")  # Call helper function

        print(f"Input Block Number: {input_number}, Input Street Name: {input_street}")

        # First, let's try to find an exact match on street name
        matching_rows = rent_df[rent_df["block_address"].str.contains(input_street, na=False, case=False)].copy()
        # Now let's use fuzzy string matching to improve street matching
        if not matching_rows.empty:
            best_match = difflib.get_close_matches(input_street, matching_rows["block_address"].tolist(), n=1, cutoff=0.7)
            if best_match:
                matching_rows = matching_rows[matching_rows["block_address"] == best_match[0]]

        matching_rows["block_num"] = pd.to_numeric(matching_rows["block_num"], errors='coerce')
        matching_rows = matching_rows.dropna(subset=["block_num"])

        # Step 1: Normalize the block number based on the input
        if input_number:
            input_block = int(input_number) // 100 * 100

        # Step 1: Extract the block number from the block_address column
            matching_rows["block_num_reference"] = matching_rows["block_address"].apply(
                lambda x: int(re.search(r'(\d+)', x).group(0)) // 100 * 100 if pd.notna(x) else None
            )

        # Step 2: Now, calculate the distance using the rounded block_num_reference
            matching_rows["distance"] = abs(matching_rows["block_num_reference"] - input_block)

        # Debug: Print out the distances for rows with the block address you're interested in
            matching_rows_sorted = matching_rows.sort_values(by="distance", ascending=True)
            print(matching_rows_sorted[["block_num", "block_address", "block_num", "distance"]])
            
            # Find the closest match
            closest_match = matching_rows.nsmallest(1, "distance")
            print("Closest Match (Debug):")
            print(closest_match)
            closest_block_address = closest_match["block_address"].iloc[0]
            print(f"Closest Block Address: {closest_block_address}")
        else:
            print("Address parsing failed - returning default map.")
            return update_map(DEFAULT_SEARCH_QUERY)  # Recursive call with default address
        

        matching_rows_with_closest_block = matching_rows[
            matching_rows["block_address"] == closest_block_address
        ]
        print("Matching Rows with Distance (Debug):\n", matching_rows)

        if matching_rows_with_closest_block.empty or matching_rows_with_closest_block["latitude"].isnull().any() or matching_rows_with_closest_block["longitude"].isnull().any():
            print("No valid coordinates or matching data - returning default map.")
            # Return default map and error message
            return update_map_with_message(DEFAULT_SEARCH_QUERY, "No valid data found. Please check the address format.")  # Call helper function
            

        # Aggregate data
        aggregated_data = matching_rows_with_closest_block.groupby("block_address").agg({
            'cleaned_monthly_rent': 'mean',
            'cleaned_square_footage': 'median',
            'cleaned_bedroom_count': 'median',
            'cleaned_bathroom_count': 'median',
            'unit_count': 'sum',
            'latitude': 'mean',
            'longitude': 'mean'
        }).reset_index()

        # Rename columns for hover data
        aggregated_data.rename(columns={
            'cleaned_monthly_rent': 'Average Monthly Rent',
            'cleaned_square_footage': 'Average Square Footage',
            'cleaned_bedroom_count': 'Average Bedroom Count',
            'cleaned_bathroom_count': 'Average Bathroom Count',
            'unit_count': 'Total Rental Units',
            'latitude': 'mean_lat',
            'longitude': 'mean_lon'
        }, inplace=True)

        print("Aggregated Data (Debug):\n", aggregated_data[["block_address", "Average Monthly Rent"]])
        

        print("Hover Data Debug:")
        print(aggregated_data[['block_address', 
                       'Average Monthly Rent', 
                       'Average Square Footage', 
                       'Average Bedroom Count', 
                       'Average Bathroom Count', 
                       'Total Rental Units']])

        # Create map
        fig = px.scatter_mapbox(
            aggregated_data,
            lat="mean_lat",
            lon="mean_lon",
            hover_name="block_address",
            size="Total Rental Units",
            color="Average Monthly Rent",
            title="Clustered Data for the Address",
            zoom=15,
            height=500,
            template="plotly"
        )
        
        fig.update_traces(
            customdata=aggregated_data[["Average Monthly Rent", "Average Square Footage", 
                                "Average Bedroom Count", "Average Bathroom Count", 
                                "Total Rental Units"]].values,  # Pass the data to customdata
            hovertemplate=(
                "<b>%{hovertext}</b><br>"  # Title is the block address
                "Total Rental Units: %{customdata[4]}<br>"  # Customdata[4] is Total Rental Units
                "Average Monthly Rent: $%{customdata[0]:.2f}<br>"  # Customdata[0] is Average Monthly Rent
                "Average Square Footage: %{customdata[1]:.2f}<br>"  # Customdata[1] is Average Square Footage
                "Average Bedroom Count: %{customdata[2]}<br>"  # Customdata[2] is Average Bedroom Count
                "Average Bathroom Count: %{customdata[3]}<br>"  # Customdata[3] is Average Bathroom Count
            ),
            marker=dict(size=20, symbol="lodging", color="blue")  # Place marker settings here
        )
        fig.update_layout(
            mapbox_style="streets",
            margin={"r": 0, "t": 0, "l": 0, "b": 0}
        )
        return fig , ""

def update_map_with_message(search_query, error_message):
    """
    Helper function to update the map with a custom error message.
    """
    # Update the map with the default location and error message
    fig = go.Figure().update_layout(
        mapbox_style="streets",
        title="Default Search: 100 Larkin St"
    )
    return fig, error_message

# Run the app
if __name__ == "__main__":
    app.run_server(debug=True)