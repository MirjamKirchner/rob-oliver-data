# import pandas as pd
# import requests
# import boto3
# import os
# import sys
# import pytz
# import difflib
# import inspect
# import tabula
# from hashlib import sha256
# from datetime import datetime
# from config import app_logger
# from pandasgui.gui import PandasGui
# from PyQt5 import QtGui
# from IPython.core.magic import register_line_magic
# from glob import glob
# from abc import ABC, abstractmethod
# from typing import List, Tuple
# from PyPDF2 import PdfFileReader
#
#
#
#
# AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
#
#
# CET = pytz.timezone("CET")  # central European Summer time
#
#
# class RobGui(PandasGui):
#     def __init__(self, settings={}, **kwargs):
#         """
#         Child class of PandasGui with a customised close event
#         :param settings: (Dict) settings
#         :param kwargs: additional keyword arguments
#         """
#         super().__init__(settings=settings, **kwargs)
#
#     def closeEvent(self, e: QtGui.QCloseEvent) -> None:
#         """
#         Stores the pre-processed data with potential manual changes in the csv-files self.path_to_rob_engineered and
#         self.path_to_finding_places, when the respective RobGui is closed.
#         :param e: (QtGui.QCloseEvent) Close event
#         :return: None
#         """
#         # Update new_rob
#         df_new_rob = self.get_dataframes()["new_rob"]
#         df_new_rob.drop("Fundort", axis=1, inplace=True)
#         df_new_rob.rename(columns={"Mapped Fundort": "Fundort"}, inplace=True)
#         df_new_rob.sort_values(by="Einlieferungsdatum", ascending=False)
#
#         # Update and save catalogued_finding_places
#         df_new_finding_places = df_new_rob[["Fundort", "Lat", "Long"]].drop_duplicates()
#         df_new_finding_places.rename(columns={"Fundort": "Name"}, inplace=True)
#         df_new_finding_places.reset_index(drop=True, inplace=True)
#         df_old_finding_places = pd.read_csv(PATH_TO_FINDING_PLACES)
#         df_updated_finding_places = pd.concat(
#             [df_old_finding_places, df_new_finding_places], ignore_index=True
#         ).drop_duplicates()
#         df_updated_finding_places.sort_values(by="Name").to_csv(
#             PATH_TO_FINDING_PLACES, index=False
#         )
#
#         super().closeEvent(e)
#
#
# class RobHistoricizer(ABC):
#     """
#     TODO describe class
#     """
#     @abstractmethod
#     def __init__(self,
#                  path_to_raw_data: str = None,
#                  path_to_changelogs: str = None,
#                  path_to_interim_data: str = None,
#                  path_to_deployment_data: str = None):
#         """
#         The RobHistorizer historizes information about seal pups rescued by the Seehundstation Friedrichskoog.
#         :param rob_scraper: (RobScraper) A RobScraper that contains raw data scraped from the website of Seehundstation
#         Friedrichskoog.
#         TODO adapt this!
#         """
#         self.path_to_raw_data = path_to_raw_data
#         self.path_to_changelogs = path_to_changelogs
#         self.path_to_interim_data = path_to_interim_data
#         self.path_to_deployment_data = path_to_deployment_data
#
#         # self.rob_scraper = rob_scraper
#         # self.latest_update = latest_update
#         # self.path_to_finding_places = path_to_finding_places
#         # self.df_historized_rob = pd.read_csv(
#         #     PATH_TO_ROB,
#         #     dtype={"Sys_geloescht": "int32"},
#         #     parse_dates=["Einlieferungsdatum", "Erstellt_am", "Sys_aktualisiert_am"],
#         #     date_parser=pd.to_datetime,
#         # )
#
#     @abstractmethod
#     def get_new_robs(self) -> List[str]:
#         """
#         Returns a list of paths to new robs pdf
#         :return:
#         """
#         pass
#
#     @abstractmethod
#     def clean_up_logs(self, logs: List[str]) -> str:
#         """
#         Removes the stated log-files from the log-folder
#         :param logs: a list of log-files
#         :return: a status message about the cleanup
#         """
#         pass
#
#     @abstractmethod
#     def get_raw_meta_data(self, path_to_raw_pdf: str) -> Tuple[int, str]:
#         """
#         Gets a list
#         :return: number of pages in PDF, the date when the PDF was created
#         """
#         # # local
#         # if path_to_raw is None:
#         #     link_to_rob = self.link_to_rob_
#         #     read = requests.get(link_to_rob)
#         #     pdf_obj = io.BytesIO(read.content)
#         # else:
#         # # S3
#         #     link_to_rob = path_to_raw
#         #     pdf_obj = open(path_to_raw, "rb")
#         # pdf_file_reader = PdfFileReader(pdf_obj)
#         # total_pages = pdf_file_reader.numPages
#         # date = pdf_file_reader.documentInfo["/ModDate"]
#         # pdf_obj.close
#         # self.date_ = datetime.strptime(date.replace("'", ""), "D:%Y%m%d%H%M%S%z")
#         pass
#
#
#     @abstractmethod
#     def get_rob(self) -> pd.DataFrame:
#         pass
#
#     def scrape_rob(self, path_to_raw_pdf: str) -> pd.DataFrame:
#         """
#         TODO revise this
#         Scrapes the current pdf-file of rescued seal pups and saves it in a pandas.DataFrame
#         :param path_to_raw: (str) Local path that identifies the link to the pdf to scrape from
#         :return: (pd.DataFrame) A pandas.DataFrame that contains information about rescued seal pups
#         """
#         try:
#             num_pages_pdf, creation_date_pdf = self.get_raw_meta_data(path_to_raw_pdf)
#
#             df_rob = pd.concat(
#                 [
#                     tabula.read_pdf(
#                         path_to_raw_pdf,
#                         pages="1",
#                         encoding="cp1252",  # Page 1
#                         area=[10, 0, 95, 100],
#                         relative_area=True,
#                         multiple_tables=False,
#                         pandas_options={
#                             "header": None,
#                             "names": [
#                                 "Fundort",
#                                 "Einlieferungsdatum",
#                                 "Tierart",
#                                 "Aktuell",
#                             ],
#                         },
#                     )[0],
#                     tabula.read_pdf(
#                         path_to_raw_pdf,
#                         pages="2-" + str(num_pages_pdf),
#                         encoding="cp1252",  # Remaining pages
#                         area=[5, 0, 95, 100],
#                         relative_area=True,
#                         multiple_tables=False,
#                         pandas_options={
#                             "header": None,
#                             "names": [
#                                 "Fundort",
#                                 "Einlieferungsdatum",
#                                 "Tierart",
#                                 "Aktuell",
#                             ],
#                         },
#                     )[0],
#                 ]
#             ).reset_index(drop=True)
#
#             df_rob["Einlieferungsdatum"] = pd.to_datetime(
#                 df_rob["Einlieferungsdatum"], format="%d.%m.%Y"
#             )
#             # TODO add erstellt am as date
#             return df_rob
#         except FileNotFoundError:
#             app_logger.exception(
#                 "The RobScraper cannot find the file specified in attribute `path_to_raw_pdf`. "
#                 "Are you sure the file exists?"
#             )
#         except Exception:
#             app_logger.exception("Unexpected exception occurred.")
#
#     def _save_rob(self, save_copy: bool):
#         """
#         Saves the historized information about rescued seal pups in the csv-file rob.csv.
#         :param save_copy: (bool) If true then a time stamp is attached to the file name, i.e., the orginal file is not
#         overwritten.
#         :return: None
#         """
#         if save_copy:
#             self.df_historized_rob.sort_values(
#                 by=["Sys_aktualisiert_am", "Einlieferungsdatum"]
#             ).to_csv(
#                 os.path.join(
#                     PATH_TO_DATA,
#                     "interim",
#                     datetime.now().strftime("%m-%d-%Y_%H-%M-%S_") + "rob.csv",
#                 ),
#                 index=False,
#             )
#         else:
#             self.df_historized_rob.sort_values(
#                 by=["Sys_aktualisiert_am", "Einlieferungsdatum"]
#             ).to_csv(os.path.join(PATH_TO_DATA, "interim", "rob.csv"), index=False)
#
#     def _show_new_rob(self, df_new_rob: pd.DataFrame, settings={}, **kwargs) -> RobGui:
#         """
#         Some preprocessing steps require human checks and, if need be, correction. This task is facilitated by opening
#         the preprocessed data in a RobGui, a customized PandasGui (see https://github.com/adamerose/pandasgui).
#
#         Objects provided as args and kwargs should be any of the following:
#         DataFrame   Show it using PandasGui
#         Series      Show it using PandasGui
#         Figure      Show it using FigureViewer. Supports figures from plotly, bokeh, matplotlib, altair
#         dict/list   Show it using JsonViewer
#         :param settings: (Dict) settings
#         :param kwargs: additional keyword arguments
#         :return: (RobGui) An instance of class RobGui
#         """
#         logger.info("Opening PandasGUI")
#         # Get the variable names in the scope show() was called from
#         callers_local_vars = inspect.currentframe().f_back.f_locals.items()
#
#         # Make a dictionary of the DataFrames from the position args and get their variable names using inspect
#         items = {"new_rob": df_new_rob}
#
#         dupes = [key for key in items.keys() if key in kwargs.keys()]
#         if any(dupes):
#             logger.warning("Duplicate names were provided, duplicates were ignored.")
#
#         kwargs = {**kwargs, **items}
#
#         pandas_gui = RobGui(settings=settings, **kwargs)
#         pandas_gui.caller_stack = inspect.currentframe().f_back
#
#         # Register IPython magic
#         try:
#
#             @register_line_magic
#             def pg(line):
#                 pandas_gui.store.eval_magic(line)
#                 return line
#
#         except Exception as e:
#             # Let this silently fail if no IPython console exists
#             if (
#                 e.args[0]
#                 == "Decorator can only run in context where `get_ipython` exists"
#             ):
#                 pass
#             else:
#                 raise e
#
#         return pandas_gui
#
#     @abstractmethod
#     def get_finding_places(self) -> pd.DataFrame:
#         # pd.read_csv(
#         #             self.path_to_finding_places, dtype={"Long": "float64", "Lat": "float64"}
#         #         )
#         pass
#
#     def preprocess_new_rob(self, df_rob: pd.DataFrame) -> pd.DataFrame:
#         """
#         Preprocesses raw data about rescued seal pups in self.rob_scraper.df_rob_ for historization
#         :return: (pd.DataFrame) Preprocessed raw data about rescued seal pups
#         """
#         # Get copy of df_new_rob
#         df_new_rob = df_rob.copy()
#
#         # Impute missing finding places with "Unknown"
#         df_new_rob["Fundort"].fillna("Unknown", inplace=True)
#         df_finding_places = self.get_finding_places()
#         mapping_finding_places = dict(
#             zip(df_finding_places["Name"], df_finding_places.index)
#         )
#
#         # Correct spelling of finding places ("Fundort") and add geo coordinates before generating IDs
#         spelling_corrected_finding_places = [
#             difflib.get_close_matches(
#                 finding_place, df_finding_places["Name"], n=1, cutoff=0.0
#             )[0]
#             for finding_place in df_new_rob["Fundort"]
#         ]
#         df_new_rob.insert(
#             loc=df_new_rob.columns.get_loc("Fundort") + 1,
#             column="Mapped Fundort",
#             value=spelling_corrected_finding_places,
#         )
#         df_new_rob.insert(
#             loc=df_new_rob.columns.get_loc("Fundort") + 2,
#             column="Lat",
#             value=df_finding_places["Lat"]
#             .iloc[
#                 [
#                     mapping_finding_places[finding_place]
#                     for finding_place in df_new_rob["Mapped Fundort"]
#                 ]
#             ]
#             .values,
#         )
#         df_new_rob.insert(
#             loc=df_new_rob.columns.get_loc("Fundort") + 3,
#             column="Long",
#             value=df_finding_places["Long"]
#             .iloc[
#                 [
#                     mapping_finding_places[finding_place]
#                     for finding_place in df_new_rob["Mapped Fundort"]
#                 ]
#             ]
#             .values,
#         )
#
#         # Double check spelling corrections and get manually corrected dataframe
#         # TODO check whether this is still working!
#         df_new_rob = self._show_new_rob(df_new_rob).get_dataframes()["new_rob"]
#
#         # Set ID as hash of "Fundort", "Lat", "Long", "Einlieferungsdatum", "Tierart" & enumeration index of the former
#         df_new_rob = df_new_rob.assign(
#             order=df_new_rob.groupby(
#                 ["Fundort", "Einlieferungsdatum", "Tierart"]
#             ).cumcount()
#         )
#         df_new_rob.insert(
#             loc=0,
#             column="Sys_id",
#             value=df_new_rob[
#                 ["Fundort", "Einlieferungsdatum", "Tierart", "order"]
#             ].apply(
#                 lambda row: sha256(
#                     row.to_string(index=False).encode("utf-8")
#                 ).hexdigest(),
#                 axis=1,
#             ),
#         )
#         df_new_rob.drop("order", inplace=True, axis=1)
#
#         assert (
#             df_new_rob["Sys_id"].nunique() == df_new_rob["Sys_id"].size
#         ), app_logger.error("Row IDs are not unique.")
#
#         # Add technical columns
#         df_new_rob["Erstellt_am"] = self.rob_scraper.date_.strftime("%Y-%m-%d %H:%M:%S")
#         df_new_rob = df_new_rob.join(
#             pd.DataFrame(
#                 {
#                     "Sys_geloescht": pd.Series(dtype="int32"),
#                     "Sys_aktualisiert_am": pd.Series(dtype="datetime64[ns]"),
#                 }
#             )
#         )
#
#         # For each row, hash non-technical columns for historization purposes
#         df_new_rob["Sys_hash"] = df_new_rob[
#             ["Sys_id", "Fundort", "Einlieferungsdatum", "Tierart", "Aktuell"]
#         ].apply(
#             lambda row: sha256(row.to_string(index=False).encode("utf-8")).hexdigest(),
#             axis=1,
#         )
#
#         self.df_new_rob_ = df_new_rob
#         return df_new_rob
#
#     def historize_rob(self, save_copy: bool = True) -> None:
#         """
#         Historizes and saves the raw data about rescued seal pups in self.rob_scraper.df_rob_
#         :param save_copy: (bool) If true then the historized data about rescued seal pups not saved in rob.csv but a
#         copy
#         :return: None
#         """
#         # Get new and old dataset
#         df_new_rob = self._preprocess_new_rob().copy()
#         df_old_rob = self.df_historized_rob.copy()
#
#         # Find already existing entries that can be ignored
#         entry_exists = df_new_rob["Sys_hash"].isin(df_old_rob["Sys_hash"])
#         if entry_exists.all():  # Abort historization procedure if nothing has changed
#             print("No changes in self.df_new_rob_ with respect to rob.csv.")
#             sys.exit(0)
#
#         # For new entries, check whether there is a matching ID
#         id_exists = df_new_rob.loc[~entry_exists, "Sys_id"].isin(df_old_rob["Sys_id"])
#
#         now = datetime.now()
#         # For old entries with location "Unknown", check whether there is an entry for which finding date with
#         # `id_exists == False`, i.e., an old entry was most likely manually corrected
#         df_old_rob_location_unknown = df_old_rob[
#             (df_old_rob["Fundort"] == "Unknown") & (df_old_rob["Sys_geloescht"] == 0)
#         ]
#
#         for index, id_flag in id_exists.items():
#             # Define new entry
#             new_entry = df_new_rob.iloc[index, :]
#             new_entry["Sys_geloescht"] = 0
#             new_entry["Sys_aktualisiert_am"] = now
#             if id_flag:  # Label deprecated entries of already existing ID as deleted
#                 df_old_rob.loc[
#                     (df_old_rob["Sys_id"] == new_entry["Sys_id"])
#                     & (df_old_rob["Sys_geloescht"] == 0),
#                     ["Sys_geloescht", "Sys_aktualisiert_am"],
#                 ] = (1, new_entry["Sys_aktualisiert_am"])
#             else:
#                 is_matching_old_entry = (
#                     df_old_rob_location_unknown["Einlieferungsdatum"]
#                     == new_entry["Einlieferungsdatum"]
#                 ) & (df_old_rob_location_unknown["Tierart"] == new_entry["Tierart"])
#                 if any(
#                     is_matching_old_entry
#                 ):  # TODO AND count seals on this Einlieferungsdatum in new and old has stayed the same
#                     idx_old = (
#                         df_old_rob_location_unknown[is_matching_old_entry]
#                         .sort_index(ascending=False)
#                         .index[0]
#                     )
#                     df_old_rob_location_unknown.drop([idx_old], inplace=True)
#                     df_old_rob.loc[
#                         idx_old, ["Sys_id", "Sys_geloescht", "Sys_aktualisiert_am"]
#                     ] = (new_entry["Sys_id"], 1, new_entry["Sys_aktualisiert_am"])
#
#             # Append new entry
#             df_old_rob = pd.concat(
#                 [df_old_rob, new_entry.to_frame().T], ignore_index=True
#             )
#
#         self.df_historized_rob = df_old_rob
#         self._save_rob(save_copy)
#
#     def update_rob(self):
#         new_robs = self.get_new_robs()
#         df_new_robs = pd.DataFrame(columns=[
#             "Sys_id",
#             "Fundort",
#             "Lat",
#             "Long",
#             "Einlieferungsdatum",
#             "Tierart",
#             "Aktuell",
#             "Erstellt_am",
#             "Sys_geloescht",
#             "Sys_aktualisiert_am",
#             "Sys_hash"
#         ])
#         for new_rob in new_robs:
#             df_new_rob = self.scrape_rob(new_rob)
#             df_new_rob = self.
#
#
# class RobHistoricizerLocal(RobHistoricizer):
#     pass
#
#
# class RobHistoricizerAWS(RobHistoricizer):
#     pass
#
#
# if __name__ == "__main__":
#     run_local = True
#     rob_historicizer = None
#     if run_local:
#         rob_historicizer = RobHistoricizerLocal()
#     else:
#         rob_historicizer = RobHistoricizerAWS()
#     rob_historicizer.update_rob(save_to_clearml=False)  # TODO integrate clear ml dataset
