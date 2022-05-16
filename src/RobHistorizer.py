import pandas as pd
import os
import sys
from hashlib import sha256
from config import PATH_TO_DATA
from datetime import datetime
from RobScraper import RobScraper

PATH_TO_ROB = os.path.join(PATH_TO_DATA, "processed/rob.csv")


class RobHistorizer:
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
        :param save_copy: If true then a time stamp is attached to the file name, i.e., the orginal file is not
        overwritten.
        :return: None
        """
        if save_copy:
            self.df_historized_rob.to_csv(os.path.join(PATH_TO_DATA, "processed",
                                                       datetime.now().strftime("%m-%d-%Y_%H-%M-%S_") + "rob.csv"),
                                          index=False)
        else:
            self.df_historized_rob.to_csv(os.path.join(PATH_TO_DATA, "processed", "rob.csv"), index=False)

    def _preprocess_new_rob(self) -> pd.DataFrame:
        # Get copy of df_rob_
        df_new_rob = self.rob_scraper.df_rob_.copy()

        # Set row number as ID
        # TODO rebase index: The PDF is sometimes reset so you cannot use the row number as index
        df_new_rob.reset_index(inplace=True)
        df_new_rob.rename(columns={"index": "Sys_id"}, inplace=True)
        df_new_rob["Sys_id"] = df_new_rob["Sys_id"].astype("int32")

        # TODO assert whether IDs are unique

        # Add technical columns
        df_new_rob["Erstellt_am"] = self.rob_scraper.date_
        df_new_rob = df_new_rob.join(pd.DataFrame({"Sys_geloescht": pd.Series(dtype="int32"),
                                                   "Sys_aktualisiert_am": pd.Series(dtype="datetime64[ns]")}))

        # For each row, hash columns that carry information for historization purposes
        df_new_rob["Sys_hash"] = df_new_rob[
            ["Sys_id", "Fundort", "Einlieferungsdatum", "Tierart", "Aktuell"]
        ].apply(lambda row: sha256(row.to_string(index=False).encode('utf-8')).hexdigest(), axis=1)

        self.df_new_rob_ = df_new_rob

        return df_new_rob

    def _sanity_check_rob(self):
        # Assumptions:
        # Entries in columns Fundort, Einlieferungsdatum, Tierart do not change over time, merely Aktuell is updated
        # No rows will be inserted 'above' the last entry from pdf to pdf
        # No rows will be deleted from the file -> You can use row numbers as ID
        pass

    def historize_rob(self, save_copy=True):

        # 1. Identify Sys_hash that are not in rob.csv
        # 2. Among the new Sys_hash, identify existing and new ids
        # 3. Update existing ids and add new ids
        # 4. Build in sanity checks:
        #   - For an id, have the columns Fundort, Einlieferungsdatum, Tierart, indeed, not changed? -> Pass
        #   - Does the new df have more entries than the old df between the earliest and latest date of the old df -> Manual check
        #   - Does the new df have more roes than the old df? -> Pass
        """
        A slightly more robust workflow might look something like this:

        For each row in in the CSV (call it SOURCE_DATA), hash the entire line and store the hash value in a separate table (call it HASHES)
        Do your data processing on the raw input data, and store the output in a separate table (call it PROCESSED_DATA) and add a column for the hash value
        Every time your source data is updated, hash each line in the new SOURCE_DATA, check if it exists in HASHES, and if it does then just move to the next line (this prevents you from reprocessing data you've already done); otherwise do your processing and add it to PROCESSED_DATA
        This workflow will work well for data sets where:

        Exact-duplicate rows don't matter
        Updates may occur on previously-released rows
        """

        df_new_rob= self._preprocess_new_rob().copy()
        df_old_rob = self.df_historized_rob.copy()

        # TODO historization Assumption: The data passes all sanity checks, i.e., all assumptions are satisfied
        # Check whether hash value already exists in old dataframe
        #   If yes, proceed to next line
        #   If no, check whether ID already exists in old dataframe and at what position
        #       If yes, set Sys_geloescht of the old entry to 1, update Sys_aktualisiert, and add the new entry with
        #       Sys_geloescht = 0
        #       If no, add new line with Sys_geloescht = 0

        # Find already existing entries that can be ignored
        entry_exists = df_new_rob["Sys_hash"].isin(df_old_rob["Sys_hash"])
        if entry_exists.all():
            print("No changes in self.df_new_rob_ with respect to rob.csv.")
            sys.exit(0)

        # For new entries, check whether there is a matching ID
        id_exists = df_new_rob.loc[~entry_exists, "Sys_id"].isin(df_old_rob["Sys_id"])

        # Append new entry and update old entries if ID already exists
        for index, id_flag in enumerate(id_exists):
            new_entry = df_new_rob.iloc[index, :]
            new_entry["Sys_geloescht"] = 0
            new_entry["Sys_aktualisiert_am"] = datetime.now()
            if id_flag:
                df_old_rob.loc[df_old_rob["Sys_id"] == new_entry["Sys_id"] & df_old_rob["Sys_id"] == 0,
                               ["Sys_geloescht", "Sys_aktualisiert_am"]] = (1, new_entry["Sys_aktualisiert_am"])
            df_old_rob = pd.concat([df_old_rob, new_entry.to_frame().T], ignore_index=True)

        self.df_historized_rob = df_old_rob
        self._save_rob(save_copy)

def main():
    rob_scraper = RobScraper()
    #rob_scraper.find_rob()
    rob_scraper.scrape_rob(local_path_to_rob=os.path.join(PATH_TO_DATA, "raw", "20220429_1.6HomepageHeuler.pdf"))
    rob_historizer = RobHistorizer(rob_scraper)
    rob_historizer._preprocess_new_rob()
    rob_historizer.historize_rob(save_copy=False)


if __name__ == "__main__":
    main()
