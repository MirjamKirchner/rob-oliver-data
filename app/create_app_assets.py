import os
import pandas as pd
from config import PATH_TO_DATA
from datetime import datetime
import numpy as np
import datetime

PATH_TO_ROB = os.path.join(PATH_TO_DATA, "interim/rob.csv")
# TODO: do not display outliers, i.e., seals that have been in Reha extraordinarily long


def _load_engineered_rob():
    df_engineered_rob = pd.read_csv(PATH_TO_ROB)
    df_engineered_rob[["Long", "Lat", "Einlieferungsdatum", "Erstellt_am", "Sys_aktualisiert_am", "Sys_geloescht"]] = \
        df_engineered_rob[
            ["Long", "Lat", "Einlieferungsdatum", "Erstellt_am", "Sys_aktualisiert_am", "Sys_geloescht"]
        ].astype(
            {"Long": "float64",
             "Lat": "float64",
             "Einlieferungsdatum": "datetime64[ns]",
             "Erstellt_am": "datetime64[ns]",
             "Sys_aktualisiert_am": "datetime64[ns]",
             "Sys_geloescht": "int32"}
        )
    return df_engineered_rob


DF_ROB = _load_engineered_rob()


# Part to whole
def create_part_to_whole(max_date: datetime = pd.to_datetime("today"),
                         min_date: datetime = pd.to_datetime("1990-04-30")):
    df_time_slice = DF_ROB.loc[(DF_ROB["Einlieferungsdatum"] >= min_date) &
                               (DF_ROB["Erstellt_am"] < max_date) &
                               (DF_ROB["Sys_geloescht"] == 0),
                               ["Erstellt_am", "Sys_id", "Sys_geloescht"]]
    df_latest_by_id = df_time_slice.set_index(pd.DatetimeIndex(df_time_slice["Erstellt_am"])).\
        groupby(["Sys_id"]).\
        last()
    return pd.merge(df_latest_by_id,
                    DF_ROB,
                    how="left",
                    on=["Erstellt_am", "Sys_id", "Sys_geloescht"])["Aktuell"].value_counts()


def create_time_series(max_date: datetime = pd.to_datetime("today"),
                       min_date: datetime = pd.to_datetime("1990-04-30")):
    df_time_series = DF_ROB[["Sys_id", "Einlieferungsdatum", "Tierart"]]. \
        drop_duplicates(). \
        groupby(["Tierart", pd.Grouper(key="Einlieferungsdatum", axis=0, freq="W-MON")]). \
        count(). \
        reset_index(). \
        rename(columns={"Einlieferungsdatum": "Einlieferungswoche", "Sys_id": "Anzahl"})
    return df_time_series[(df_time_series["Einlieferungswoche"] >= min_date) &
                          (df_time_series["Einlieferungswoche"] < max_date)]


def create_bubbles(max_date: datetime = pd.to_datetime("today"),
                   min_date: datetime = pd.to_datetime("1990-04-30")):
    df_bubbles = DF_ROB[["Sys_id", "Einlieferungsdatum", "Long", "Lat"]]. \
        drop_duplicates(). \
        groupby(["Long", "Lat", pd.Grouper(key="Einlieferungsdatum", axis=0, freq="W-MON")]). \
        count(). \
        reset_index(). \
        rename(columns={"Sys_id": "Anzahl"})
    df_bubbles = pd.merge(df_bubbles, DF_ROB[["Long", "Lat", "Fundort"]].drop_duplicates(),
                          how="left",
                          on=["Long", "Lat"])
    return df_bubbles[(df_bubbles["Einlieferungsdatum"] >= min_date) &
                      (df_bubbles["Einlieferungsdatum"] < max_date)]


def get_marks(min_date, max_date):
    """Convert DateTimeIndex to a dict that maps epoch to str

    Parameters:
        df (Pandas DataFrame): df with index of type DateTimeIndex

    Returns:
        dict: format is {
            1270080000: '04-2010',
            1235865600: '03-2009',
             ...etc.
        }
    """
    months = pd.date_range(min_date, max_date, freq='MS').to_period("M").unique().sort_values()
    epochs = months.to_timestamp().astype(np.int64) // 10**9
    strings = months.strftime("%m-%Y")
    return dict(zip(epochs, strings))


if __name__ == "__main__":
    r = get_marks(pd.Timestamp(DF_ROB["Einlieferungsdatum"].min()),
                  pd.Timestamp(DF_ROB["Erstellt_am"].max()))
    print(r)
