import os

from RobScraper import RobScraper
from RobHistorizer import RobHistorizer
from clearml import Task, Dataset
from config import PATH_TO_DATA

PROJECT_NAME = "rob-oliver"
DATASET_NAME = "rob"
PATH_TO_ROB = os.path.join(PATH_TO_DATA, "interim/rob.csv")


def _update_rob_file_system(path_to_raw: str = None):
    """
    Updates the file in PATH_TO_ROB.
    :param path_to_raw: (str) Optional path to a local pdf-file containing information about rescued seal pups. If None,
    the function scrapes the current version from the website.
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


def update_rob_clearml(path_to_raw=None, path_to_rob=PATH_TO_ROB):
    """
    Controls the version of the data in PATH_TO_ROB using clearml's Dataset-
    class (https://clear.ml/docs/latest/docs/references/sdk/dataset).
    :param path_to_raw: (str) Optional path to a local pdf-file containing information about rescued seal pups. If None,
    the function scrapes the current version from the website.
    :param path_to_rob: (str) Path to a csv-file in which the data is to be stored
    :return: None
    """
    _update_rob_file_system(path_to_raw=path_to_raw)

    dataset = Dataset.create(
        dataset_name="rob",
        dataset_project=PROJECT_NAME,
        parent_datasets=[Dataset.get(dataset_project=PROJECT_NAME, dataset_name=DATASET_NAME).id]
    )
    dataset_task = Task.get_task(task_id=dataset.id)
    dataset.add_files(path_to_rob)  # Add the local files
    dataset.finalize(auto_upload=True)  # Finalize and upload the data
    dataset_task.flush(wait_for_uploads=True)  # Make sure we wait until everything is uploaded


if __name__ == "__main__":
    #update_rob_clearml(path_to_raw=os.path.join(PATH_TO_DATA, "raw", "20220429_1.6HomepageHeuler.pdf"))
    update_rob_clearml()
