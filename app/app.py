# Run this app with `python app.py` and
# visit http://127.0.0.1:8050/ in your web browser.

from dash import Dash, html, dcc, Input, Output
from plotly.subplots import make_subplots
from flask import send_from_directory
import plotly.express as px
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import pandas as pd
import folium as fm
from datetime import datetime

from create_app_assets import create_part_to_whole, create_time_series, create_bubbles, get_marks, DF_ROB
import plotly.io as pio

pio.templates.default = "simple_white"


# Part to whole

# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(1,1)"), row=1, col=1)
# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(1,2)"), row=1, col=2)
# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(2,1)"), row=2, col=1)
# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(3,1)"), row=3, col=1)
# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(5,1)"), row=5, col=1)
# fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2], name="(5,2)"), row=5, col=2)

# fig.update_layout(
#     margin=dict(l=20, r=20, t=20, b=20),
#     paper_bgcolor="#869fb5"
# )

df_time_series = create_time_series()

# App
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, "/static/seehundstation_friedrichskoog.css"])

app.layout = html.Div([
    html.Img(src="/static/img/Seehundheader1.jpg"),
    html.Div([
        html.Small(children=["Daten werden bereitgestellt durch ",
                             html.A(
                                 href="https://www.seehundstation-friedrichskoog.de/",
                                 children="Seehundstation Friedrichskoog. ",
                                 style={"color": "#004d9e"}
                             ),
                             "Zuletzt aktualisiert am DATE OF THE LAST UPDATE"]
                   )
    ], style={"background-color": "#e9e2d8"}),
    html.Div(html.P("")),
    html.Div(
        [
            dbc.Container(dbc.Card(
                [

                        html.Div([
                            html.Div(
                                [
                                    dbc.Row(
                                        [
                                            dbc.Col(html.Div(
                                                dcc.Graph(id="fig-part-to-whole"),
                                                style={"width": "100%", "height": "400px"}),
                                                width=3),
                                            dbc.Col(html.Div([html.P(["Willkommen Robben-Freund!", html.Br(),
                                                                      "Hier kannst du Informationen zu den Robbenfunden der Seehundstation in Friedrichskoog untersuchen."]),
                                                              html.P(["Im Diagramm links siehst du den Anteil in Reha befindlichen, ausgewilderten und verstorbenen Robben "
                                                                      "im Zeitraum VON BIS.", html.Br(),
                                                                      "Unter diesem Text siehst du eine Karte, in der die ungefähren Fundorte der eingelieferten Robben "
                                                                      "eingetragen sind.", html.Br(),
                                                                      "Im letzten Bild kannst du dir ansehen, wann wie viele Robben in die Station eingeliefert worden sind."]),
                                                             html.P(["Zusätzlich findest du am Ende dieser Seite einen Zeitstrahl, der anzeigt für welchen Zeitraum Informationen"
                                                                     " in den Grafiken dargestellt werden. Wenn du ein bestimmtest Zeitfenster genauer betrachten möchtest,"
                                                                     " musst du nur den linken und rechten Kreis verschieben, um den Start- bzw. den Endzeitpunkt "
                                                                     "anzupassen.", html.Br(),
                                                                     "Probier es doch mal aus :-) Viel Spaß!"])])),
                                        ]
                                    )
                                ]
                            ),
                            html.Div(dbc.Card(dcc.Graph(id="fig-bubbles"))),
                            html.Div(dcc.Graph(id="fig-time-series")),
                            html.Div(dcc.RangeSlider(
                                allowCross=False,
                                id="date-slider",
                                min=pd.Timestamp(
                                    DF_ROB["Einlieferungsdatum"].min() - pd.Timedelta(days=14)).timestamp(),
                                max=pd.Timestamp(
                                    DF_ROB["Einlieferungsdatum"].max() + pd.Timedelta(days=14)).timestamp(),
                                marks=get_marks(df_time_series.set_index("Admission date")), )
                            )
                        ])

                ], color="#e9e2d8", style={"border-radius": "10px"})
            )
        ]
    ),
    html.Div(html.P(""))
    # html.Div(id="out-date-slider")
])


# @app.callback(
#     Output("out-date-slider", "children"),
#     [Input("date-slider", "value")])
# def update_output(value):
#     if value is None:
#         return 'You have selected "{}"'.format(value)
#     else:
#         return 'You have selected "{}"'.format((datetime.fromtimestamp(value[0]), datetime.fromtimestamp(value[1])))


@app.callback(
    Output("fig-part-to-whole", "figure"),
    Input("date-slider", "value"))
def update_fig_part_to_whole(selected_range):
    if selected_range is None:
        ds_part_to_whole = create_part_to_whole()
    else:
        min_date = datetime.fromtimestamp(selected_range[0])
        max_date = datetime.fromtimestamp(selected_range[1])
        ds_part_to_whole = create_part_to_whole(max_date=max_date, min_date=min_date)

    fig_part_to_whole = go.Figure(data=[go.Pie(labels=ds_part_to_whole.index,
                                               values=ds_part_to_whole.values,
                                               hole=0.4,
                                               marker_colors=["#1F4591", "#2B6AD0", "#68A4F1"])])
    fig_part_to_whole.update_layout(
        showlegend=False,
        annotations=[dict(
            text="no data<br>available" if ds_part_to_whole.sum() == 0 else str(ds_part_to_whole.sum()) + "<br>in total",
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            ax=0,
            ay=0,
            font_size=22,
            showarrow=False)],
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)"
    )

    return fig_part_to_whole


@app.callback(
    Output("fig-bubbles", "figure"),
    Input("date-slider", "value"))
def update_fig_bubbles(selected_range):
    if selected_range is None:
        df_bubbles = create_bubbles()
    else:
        min_date = datetime.fromtimestamp(selected_range[0])
        max_date = datetime.fromtimestamp(selected_range[1])
        df_bubbles = create_bubbles(max_date=max_date, min_date=min_date)

    fig_bubbles = px.scatter_mapbox(df_bubbles,
                                    lat="Lat",
                                    lon="Long",
                                    size="Count",
                                    zoom=7,
                                    center={"lat": 54.43388, "lon": 9.57109})
    fig_bubbles.update_traces(
        marker=dict(
            color="#FF7F3F",
            allowoverlap=True
        )
    )
    fig_bubbles.update_layout(
        mapbox_style="open-street-map",
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)"
    )
    return fig_bubbles


@app.callback(
    Output("fig-time-series", "figure"),
    Input("date-slider", "value"))
def update_fig_time_series(selected_range):
    if selected_range is None:
        df_time_series_slider = df_time_series
    else:
        min_date = datetime.fromtimestamp(selected_range[0])
        max_date = datetime.fromtimestamp(selected_range[1])
        df_time_series_slider = create_time_series(max_date=max_date, min_date=min_date)
    color_discrete_map = {"Seehund": "#086E7D", "Kegelrobbe": "#34BE82", "sonstige": "#F47340"}
    fig_time_series = px.line(df_time_series_slider,
                              x="Admission date",
                              y="Count",
                              color="Breed",
                              markers=True,
                              color_discrete_map=color_discrete_map)
    fig_time_series.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        ),
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)"
    )
    return fig_time_series


if __name__ == '__main__':
    app.run_server(debug=True)