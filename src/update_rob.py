import os
import pandas as pd

from RobScraper import RobScraper
from RobHistorizer import RobHistorizer
from RobEngineer import RobEngineer
from clearml import Task, Dataset
from config import PATH_TO_DATA
from datetime import datetime

PROJECT_NAME = "rob-oliver"
DATASET_NAME = "rob"
PATH_TO_ROB = os.path.join(PATH_TO_DATA, "interim/rob.csv")
PATH_TO_ROB_ENGINEERED = os.path.join(PATH_TO_DATA, "processed/rob_engineered.csv")
PATH_TO_FINDING_PLACES = os.path.join(PATH_TO_DATA, "processed/catalogued_finding_places.csv")


def _update_rob_file_system(path_to_raw: str,
                            path_to_rob: str,
                            path_to_rob_engineered: str,
                            path_to_finding_places: str,
                            latest_update: datetime) -> (RobScraper, RobHistorizer):
    """
    Updates the file in PATH_TO_ROB.
    :param path_to_raw: (str) Path to a local pdf-file containing information about rescued seal pups. If None,
    the function scrapes the current version from the website.
    :param path_to_rob: (str) Path to a csv-file in which the web-scraped data is to be stored
    :param path_to_rob_engineered: (str) Path to a csv-file in which the preprocessed data used is to be stored
    :param path_to_finding_places: (str) Path to a csv-file in which the finding places of seal pups are catalogued
    :param latest_update: (datetime) The date after which entries in the csv-file stored in path_to_rob_engineered are
    computed
    :return: None
    """
    # Scrape data
    rob_scraper = RobScraper()
    if path_to_raw is None:
        rob_scraper.find_rob()
    rob_scraper.scrape_rob(path_to_raw=path_to_raw)
    # Historize data
    rob_historizer = RobHistorizer(rob_scraper)
    rob_historizer.historize_rob(save_copy=False)

    return rob_scraper, rob_historizer


def update_rob_clearml(path_to_raw: str = None,
                       path_to_rob: str = PATH_TO_ROB,
                       path_to_rob_engineered: str = PATH_TO_ROB_ENGINEERED,
                       path_to_finding_places: str = PATH_TO_FINDING_PLACES,
                       latest_update: datetime = None) -> None:
    """
    Controls the version of the data in PATH_TO_ROB using clearml's Dataset-
    class (https://clear.ml/docs/latest/docs/references/sdk/dataset).
    :param path_to_raw: (str) Optional path to a local pdf-file containing information about rescued seal pups. If None,
    the function scrapes the current version from the website.
    :param path_to_rob: (str) Path to a csv-file in which the web-scraped data is to be stored
    :param path_to_rob_engineered: (str) Path to a csv-file in which the preprocessed data used is to be stored
    :param path_to_finding_places: (str) Path to a csv-file in which the finding places of seal pups are catalogued
    :param latest_update: (datetime) The date after which entries in the csv-file stored in path_to_rob_engineered are
    computed
    :return: None
    TODO update doc string
    """
    # Get latest update in rob engineered
    if latest_update is None:
        latest_update = pd.read_csv(path_to_rob_engineered,
                                    parse_dates=["Einlieferungsdatum",
                                                 "Erstellt_am",
                                                 "Sys_aktualisiert_am"],
                                    date_parser=pd.to_datetime)["Sys_aktualisiert_am"].max()
        latest_update = pd.to_datetime("1990-04-30") if (latest_update !=
                                                         latest_update) else latest_update
    print(latest_update)


    # Update local files
    _update_rob_file_system(path_to_raw,
                            path_to_rob,
                            path_to_rob_engineered,
                            path_to_finding_places,
                            latest_update)

    # Create clear ML dataset
    dataset = Dataset.create(
        dataset_name="rob",
        dataset_project=PROJECT_NAME,
        parent_datasets=[Dataset.get(dataset_project=PROJECT_NAME, dataset_name=DATASET_NAME).id]
    )
    dataset_task = Task.get_task(task_id=dataset.id)

    # Add the local files
    dataset.add_files(path_to_rob)
    dataset.add_files(path_to_finding_places)

    # Finalize and upload the data
    dataset.finalize(auto_upload=True)
    dataset_task.flush(wait_for_uploads=True)  # Make sure we wait until everything is uploaded


if __name__ == "__main__":
    # update_rob_clearml(path_to_raw=os.path.join(PATH_TO_DATA, "raw", "20220429_1.6HomepageHeuler.pdf"))
    #update_rob_clearml()
    dataset = Dataset.create(
        dataset_name="rob",
        dataset_project=PROJECT_NAME,
        parent_datasets=[Dataset.get(dataset_project=PROJECT_NAME, dataset_name=DATASET_NAME).id]
    )
    dataset_task = Task.get_task(task_id=dataset.id)

    # Add the local files
    dataset.add_files(PATH_TO_ROB)
    dataset.add_files(PATH_TO_FINDING_PLACES)

    # Finalize and upload the data
    dataset.finalize(auto_upload=True)
    dataset_task.flush(wait_for_uploads=True)  # Make sure we wait until everything is uploaded

