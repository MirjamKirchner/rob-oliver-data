import inspect
import logging
import pandas as pd
import os
import difflib
import numpy as np

from pandasgui.gui import PandasGui
from PyQt5 import QtGui
from IPython.core.magic import register_line_magic
from config import PATH_TO_DATA
from datetime import datetime

logger = logging.getLogger(__name__)
PATH_TO_ROB = os.path.join(PATH_TO_DATA, "interim/rob.csv")
PATH_TO_ROB_ENGINEERED = os.path.join(PATH_TO_DATA, "processed/rob_engineered.csv")
PATH_TO_FINDING_PLACES = os.path.join(PATH_TO_DATA, "processed/catalogued_finding_places.csv")

DF_FINDING_PLACES = pd.read_csv(PATH_TO_FINDING_PLACES, dtype={"Long": "float64", "Lat": "float64"})
MAPPING_FINDING_PLACES = dict(zip(DF_FINDING_PLACES["Name"], DF_FINDING_PLACES.index))


class RobGui(PandasGui):
    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        df_engineered_rob = self.get_dataframes()["rob_engineered"]
        df_engineered_rob.drop("Fundort", axis=1, inplace=True)
        df_engineered_rob.rename(columns={"Mapped Fundort": "Fundort"}, inplace=True)
        # TODO check if a new location has been added to the dataframe and if so update catalogued finding places

        df_engineered_rob.sort_values(
            by=["Sys_aktualisiert_am", "Einlieferungsdatum"]
        ).to_csv(PATH_TO_ROB_ENGINEERED, index=False)

        super().closeEvent(e)


class RobEngineer:
    """
    TODO Comment
    """
    def __init__(self, earliest_update: datetime = pd.to_datetime("1990-04-30")):
        """
        TODO Comment
        :param earliest_update:
        """
        self.earliest_update = earliest_update
        df_historized_rob = (pd.read_csv(PATH_TO_ROB,
                                         dtype={"Sys_geloescht": "int32"},
                                         parse_dates=["Einlieferungsdatum",
                                                      "Erstellt_am",
                                                      "Sys_aktualisiert_am"],
                                         date_parser=pd.to_datetime)
                             [lambda x: x["Sys_aktualisiert_am"] >= earliest_update])

        self.df_engineered_rob = (pd.read_csv(PATH_TO_ROB_ENGINEERED,
                                              dtype={
                                                  "Long": "float64",
                                                  "Lat": "float64",
                                                  "Sys_geloescht": "int32"
                                              },
                                              parse_dates=["Einlieferungsdatum",
                                                           "Erstellt_am",
                                                           "Sys_aktualisiert_am"],
                                              date_parser=pd.to_datetime)
                                  [lambda x: x["Sys_aktualisiert_am"] < earliest_update])
        self.df_engineered_rob = pd.concat([self.df_engineered_rob, df_historized_rob], axis=0)

    def _geoparse_rob(self) -> None:
        """
        TODO Comment
        :return:
        """
        self.df_engineered_rob.insert(loc=self.df_engineered_rob.columns.get_loc("Fundort")+1,
                                      column="Mapped Fundort",
                                      value=np.nan)

        slice = self.df_engineered_rob["Sys_aktualisiert_am"] >= self.earliest_update
        indices = self.df_engineered_rob.loc[slice, "Fundort"].dropna().index

        for idx in indices:
            closest_match = \
                difflib.get_close_matches(self.df_engineered_rob.at[idx, "Fundort"], DF_FINDING_PLACES["Name"],
                                          n=1,
                                          cutoff=0.0)[0]
            self.df_engineered_rob.at[idx, "Mapped Fundort"] = closest_match
            self.df_engineered_rob.at[idx, "Lat"] = DF_FINDING_PLACES.at[MAPPING_FINDING_PLACES[closest_match], "Lat"]
            self.df_engineered_rob.at[idx, "Long"] = DF_FINDING_PLACES.at[MAPPING_FINDING_PLACES[closest_match], "Long"]

    def _show_rob_engineered(self, settings={}, **kwargs) -> RobGui:
        """
        Objects provided as args and kwargs should be any of the following:
        DataFrame   Show it using PandasGui
        Series      Show it using PandasGui
        Figure      Show it using FigureViewer. Supports figures from plotly, bokeh, matplotlib, altair
        dict/list   Show it using JsonViewer
        """
        logger.info("Opening PandasGUI")
        # Get the variable names in the scope show() was called from
        callers_local_vars = inspect.currentframe().f_back.f_locals.items()

        # Make a dictionary of the DataFrames from the position args and get their variable names using inspect
        items = {"rob_engineered": self.df_engineered_rob}

        dupes = [key for key in items.keys() if key in kwargs.keys()]
        if any(dupes):
            logger.warning("Duplicate names were provided, duplicates were ignored.")

        kwargs = {**kwargs, **items}

        pandas_gui = RobGui(settings=settings, **kwargs)
        pandas_gui.caller_stack = inspect.currentframe().f_back

        # Register IPython magic
        try:
            @register_line_magic
            def pg(line):
                pandas_gui.store.eval_magic(line)
                return line

        except Exception as e:
            # Let this silently fail if no IPython console exists
            if e.args[0] == 'Decorator can only run in context where `get_ipython` exists':
                pass
            else:
                raise e

        return pandas_gui


if __name__ == "__main__":
    #from pandasgui.datasets import pokemon
    rob_engineer = RobEngineer(earliest_update=pd.to_datetime("2022-07-01"))
    rob_engineer._geoparse_rob()
    rob_engineer._show_rob_engineered()
