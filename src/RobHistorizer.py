import pandas as pd
import os
import sys
from hashlib import sha256
from config import PATH_TO_DATA
from datetime import datetime
from RobScraper import RobScraper
from config import app_logger

PATH_TO_ROB = os.path.join(PATH_TO_DATA, "processed/rob.csv")


class RobHistorizer:
    """
        The RobHistorizer historizes information about seal pups rescued by the Seehundstation Friedrichskoog.
     """
    def __init__(self, rob_scraper: RobScraper):
        self.rob_scraper = rob_scraper
        self.df_historized_rob = pd.read_csv(PATH_TO_ROB)
        self.df_historized_rob[["Einlieferungsdatum", "Erstellt_am", "Sys_aktualisiert_am", "Sys_geloescht"]] = \
            self.df_historized_rob[["Einlieferungsdatum", "Erstellt_am", "Sys_aktualisiert_am", "Sys_geloescht"]].astype(
                {"Einlieferungsdatum": "datetime64[ns]",
                 "Erstellt_am": "datetime64[ns]",
                 "Sys_aktualisiert_am": "datetime64[ns]",
                 "Sys_geloescht": "int32"}
            )

    def _save_rob(self, save_copy: bool):
        """
        Saves the historized information about rescued seal pups in the csv-file rob.csv.
        :param save_copy (bool): If true then a time stamp is attached to the file name, i.e., the orginal file is not
        overwritten.
        :return: None
        """
        if save_copy:
            self.df_historized_rob.sort_values(
                by=["Sys_aktualisiert_am", "Einlieferungsdatum"]
            ).to_csv(os.path.join(PATH_TO_DATA, "processed", datetime.now().strftime("%m-%d-%Y_%H-%M-%S_") + "rob.csv"),
                     index=False)
        else:
            self.df_historized_rob.sort_values(
                by=["Sys_aktualisiert_am", "Einlieferungsdatum"]
            ).to_csv(os.path.join(PATH_TO_DATA, "processed", "rob.csv"), index=False)

    def _preprocess_new_rob(self) -> pd.DataFrame:
        """
        Preprocesses raw data about rescued seal pups in self.rob_scraper.df_rob_ for historization
        :return (pd.DataFrame): Preprocessed raw data about rescued seal pups
        """
        # Get copy of df_rob_
        df_new_rob = self.rob_scraper.df_rob_.copy()

        # Set ID as hash of "Fundort", "Einlieferungsdatum", "Tierart" and enumeration index of the former
        df_new_rob = df_new_rob.assign(order=df_new_rob.groupby(["Fundort", "Einlieferungsdatum",
                                                                   "Tierart"]).cumcount())
        df_new_rob.insert(loc=0,
                          column="Sys_id",
                          value=df_new_rob[
                              ["Fundort", "Einlieferungsdatum", "Tierart", "order"]
                          ].apply(lambda row: sha256(row.to_string(index=False).encode('utf-8')).hexdigest(), axis=1))
        df_new_rob.drop("order", inplace=True, axis=1)

        assert df_new_rob["Sys_id"].nunique() == df_new_rob["Sys_id"].size, app_logger.error("Row IDs are not unique.")

        # Add technical columns
        df_new_rob["Erstellt_am"] = self.rob_scraper.date_
        df_new_rob = df_new_rob.join(pd.DataFrame({"Sys_geloescht": pd.Series(dtype="int32"),
                                                   "Sys_aktualisiert_am": pd.Series(dtype="datetime64[ns]")}))

        # For each row, hash columns non-technical columns for historization purposes
        df_new_rob["Sys_hash"] = df_new_rob[
            ["Sys_id", "Fundort", "Einlieferungsdatum", "Tierart", "Aktuell"]
        ].apply(lambda row: sha256(row.to_string(index=False).encode('utf-8')).hexdigest(), axis=1)

        self.df_new_rob_ = df_new_rob

        return df_new_rob

    def historize_rob(self, save_copy=True):
        """
        Historizes and saves the raw data about rescued seal pups in self.rob_scraper.df_rob_
        :param save_copy (bool): If true then the historized data about rescued seal pups not saved in rob.csv but a copy
        :return: None
        """
        # Get new and old dataset
        df_new_rob = self._preprocess_new_rob().copy()
        df_old_rob = self.df_historized_rob.copy()

        # Find already existing entries that can be ignored
        entry_exists = df_new_rob["Sys_hash"].isin(df_old_rob["Sys_hash"])
        if entry_exists.all():  # Abort historization procedure if nothing has changed
            print("No changes in self.df_new_rob_ with respect to rob.csv.")
            sys.exit(0)

        # For new entries, check whether there is a matching ID
        id_exists = df_new_rob.loc[~entry_exists, "Sys_id"].isin(df_old_rob["Sys_id"])

        now = datetime.now()
        for index, id_flag in id_exists.items():
            # Define new entry
            new_entry = df_new_rob.iloc[index, :]
            new_entry["Sys_geloescht"] = 0
            new_entry["Sys_aktualisiert_am"] = now
            if id_flag:  # Label deprecated entries of already existing ID as deleted
                df_old_rob.loc[(df_old_rob["Sys_id"] == new_entry["Sys_id"]) & (df_old_rob["Sys_geloescht"] == 0),
                               ["Sys_geloescht", "Sys_aktualisiert_am"]] = 1, new_entry["Sys_aktualisiert_am"]
            # Append new entry
            df_old_rob = pd.concat([df_old_rob, new_entry.to_frame().T], ignore_index=True)

        self.df_historized_rob = df_old_rob
        self._save_rob(save_copy)


def main():
    rob_scraper = RobScraper()
    rob_scraper.find_rob()
    #rob_scraper.scrape_rob(local_path_to_rob=os.path.join(PATH_TO_DATA, "raw", "20220429_1.6HomepageHeuler.pdf"))
    rob_scraper.scrape_rob()
    rob_historizer = RobHistorizer(rob_scraper)
    rob_historizer.historize_rob(save_copy=False)


if __name__ == "__main__":
    main()
