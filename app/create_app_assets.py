import os
import pandas as pd
from config import PATH_TO_DATA
from datetime import datetime
import numpy as np
import datetime

PATH_TO_ROB_ENGINEERED = os.path.join(PATH_TO_DATA, "processed/rob_engineered.csv")


def _load_engineered_rob():
    df_engineered_rob = pd.read_csv(PATH_TO_ROB_ENGINEERED)
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


DF_ENGINEERED_ROB = _load_engineered_rob()


# Part to whole
def create_part_to_whole(max_date: datetime = pd.to_datetime("today"),
                         min_date: datetime = pd.to_datetime("1990-04-30")):
    df_time_slice = DF_ENGINEERED_ROB.loc[(DF_ENGINEERED_ROB["Einlieferungsdatum"] >= min_date) &
                                          (DF_ENGINEERED_ROB["Erstellt_am"] < max_date) &
                                          (DF_ENGINEERED_ROB["Sys_geloescht"] == 0),
                                          ["Erstellt_am", "Sys_id", "Sys_geloescht"]]
    df_latest_by_id = df_time_slice.set_index(pd.DatetimeIndex(df_time_slice["Erstellt_am"])).\
        groupby(["Sys_id"]).\
        last()
    return pd.merge(df_latest_by_id,
                    DF_ENGINEERED_ROB,
                    how="left",
                    on=["Erstellt_am", "Sys_id", "Sys_geloescht"])["Aktuell"].value_counts()


def create_time_series(max_date: datetime = pd.to_datetime("today"),
                       min_date: datetime = pd.to_datetime("1990-04-30")):
    df_time_series = DF_ENGINEERED_ROB[["Sys_id", "Einlieferungsdatum", "Tierart"]]. \
        drop_duplicates(). \
        groupby(["Tierart", pd.Grouper(key="Einlieferungsdatum", axis=0, freq="W-MON")]). \
        count(). \
        reset_index(). \
        rename(columns={"Tierart": "Breed", "Einlieferungsdatum": "Admission date", "Sys_id": "Count"})
    return df_time_series[(df_time_series["Admission date"] >= min_date) &
                          (df_time_series["Admission date"] < max_date)]


def create_bubbles(max_date: datetime = pd.to_datetime("today"),
                   min_date: datetime = pd.to_datetime("1990-04-30")):
    df_bubbles = DF_ENGINEERED_ROB[["Sys_id", "Einlieferungsdatum", "Long", "Lat"]]. \
        drop_duplicates(). \
        groupby(["Long", "Lat", pd.Grouper(key="Einlieferungsdatum", axis=0, freq="W-MON")]). \
        count(). \
        reset_index(). \
        rename(columns={"Einlieferungsdatum": "Admission date", "Sys_id": "Count"})
    df_bubbles = pd.merge(df_bubbles, DF_ENGINEERED_ROB[["Long", "Lat", "Fundort"]].drop_duplicates(),
                          how="left",
                          on=["Long", "Lat"]).\
        rename(columns={"Fundort": "Finding place"})
    return df_bubbles[(df_bubbles["Admission date"] >= min_date) &
                      (df_bubbles["Admission date"] < max_date)]


def get_marks(df):
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
    # extract unique month/year combinations as a PeriodIndex
    months = df.index.to_period("M").unique().sort_values()

    # convert PeriodIndex to epoch series and MM-YYYY string series
    epochs = months.to_timestamp().astype(np.int64) // 10**9
    strings = months.strftime("%m-%Y")
    d = dict(zip(epochs, strings))

    return dict(zip(epochs, strings))


if __name__ == "__main__":
    create_time_series()
