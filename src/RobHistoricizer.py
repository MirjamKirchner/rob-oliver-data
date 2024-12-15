import difflib
import glob
import io
import os
import sys
from abc import ABC, abstractmethod
from copy import copy
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict, List, Tuple

import boto3
import botocore
import numpy as np
import pandas as pd
import tabula
from PyPDF2 import PdfReader
from clearml import Dataset
from pandasgui import show
from typing_extensions import Literal

PROJECT_NAME = "rob-oliver"
DATASET_NAME = "rob"
PATH_TO_OUT = "../data/out"


class RobHistoricizer(ABC):
    @abstractmethod
    def __init__(
        self,
        path_to_raw_data: str,
        path_to_changelogs: str,
        path_to_interim_data: str,
        path_to_deployment_data: str,
        path_join: str,
    ):
        """c
        The abstract base class to historicize information about seal pups rescued by the Seehundstation Friedrichskoog.

        Parameters
        ----------
        path_to_raw_data
            File path to the raw data, i.e., the folder that contains pdf files saved from
            'https://www.seehundstation-friedrichskoog.de/wp-content/heuler/1.6HomepageHeuler.pdf' at different points
            in time.

        path_to_changelogs
            File path to the changelog files. In their file names, these indicate which raw pdf files have not been
            historicized, yet.

        path_to_interim_data
            File path to data which is used, e.g., during pre-processing, but not in deployment.

        path_to_deployment_data
            File path to data which is used in deployment, e.g., in a dashboard.

        path_join
            Delimiter by which file paths should be joined,e.g., "/" or "\".
        """
        # File paths
        self.path_to_raw_data = path_to_raw_data
        self.path_to_changelogs = path_to_changelogs
        self.path_to_interim_data = path_to_interim_data
        self.path_to_deployment_data = path_to_deployment_data
        self.path_join = path_join

        # Existing data
        self.changelogs = self._get_changelogs()
        self.rob_raw = [self._get_rob_raw(changelog) for changelog in self.changelogs]
        self.df_finding_places = self._read_csv(
            path_join.join([path_to_interim_data, "catalogued_finding_places.csv"])
        )
        df_finding_place_corrections = self._read_csv(
            path_join.join([path_to_interim_data, "finding_place_corrections.csv"])
        )
        self.dict_finding_place_corrections = self._create_corrections_dict(df_finding_place_corrections)
        df_rob_historicized = self._read_csv(
            path_join.join([path_to_deployment_data, "rob.csv"])
        ).astype(
            {
                "Long": "float64",
                "Lat": "float64",
                "Einlieferungsdatum": "datetime64[ns]"
            }
        )
        self.df_rob_historicized = df_rob_historicized.assign(
            Erstellt_am=pd.to_datetime(df_rob_historicized["Erstellt_am"]),
            Sys_aktualisiert_am=pd.to_datetime(df_rob_historicized["Sys_aktualisiert_am"])
        )

        # Interim and new data (to be filled during processing)
        self.df_rob_cleaned = None
        self.df_new_rob_historicized = None
        self.df_new_finding_places = None
        self.dict_new_finding_place_corrections = None

    @abstractmethod
    def _get_changelogs(self) -> List[str]:
        """
        Gets the names of changelog files in `self.path_to_changelogs`. A changelog-file is named in the pattern
        yyyymmdd_1.6HomepageHeuler.log. For each changelog file in `path_to_changelogs` there exists a pdf file
        yyyymmdd_1.6HomepageHeuler.pdf in `self.path_to_raw` that has not been historicized, yet.

        Returns
        -------
        A list of changelog-file names.
        """
        raise NotImplementedError

    @abstractmethod
    def _delete_changelog(self, changelog_name: str) -> None:
        """
        Deletes the file with name `changelog_name` in `self.path_to_changelogs`.

        Parameters
        ----------
        changelog_name
            Name of a changelog-file that should follow the pattern yyyymmdd_1.6HomepageHeuler.log.

        Returns
        -------
        None
        """
        raise NotImplementedError

    @abstractmethod
    def _get_rob_raw(self, changelog_name: str) -> io.BytesIO:
        """
        Returns raw data stored in pdf files in folder `self.path_to_raw_data`. Data are only retrieved if there exists
        a pdf file whose name matches with `changelog_name`.

        Parameters
        ----------
        changelog_name
            Name of a changelog-file that should follow the pattern yyyymmdd_1.6HomepageHeuler.log.

        Returns
        -------
        A`BytesIO`-object that describes a raw pdf file holding information about rescued seal pups.
        """
        raise NotImplementedError

    @staticmethod
    def _create_corrections_dict(df_finding_place_corrections: pd.DataFrame) -> Dict[str, str]:
        return dict(
            zip(
                df_finding_place_corrections["Original"].to_list(),
                df_finding_place_corrections["Correction"].to_list()
            )
        )


    @abstractmethod
    def _read_csv(self, path_to_csv: str) -> pd.DataFrame:
        """
        Reads the comma-separated-values (csv) file stored in `path_to_csv`.

        Parameters
        ----------
        path_to_csv
            A path to a csv-file.

        Returns
        -------
        A `pandas DataFrame` containing the information stored in `path_to_csv`.

        """
        raise NotImplementedError

    @staticmethod
    def read_rob_raw(pdf_file: io.BytesIO) -> pd.DataFrame:
        """
        Reads the raw data from a BytesIO-object of a pdf file like
        'https://www.seehundstation-friedrichskoog.de/wp-content/heuler/1.6HomepageHeuler.pdf' into a
        `pandas DataFrame` with columns
            - `Einlieferungsdatum`: date of admittance,
            - `Fundort`: name of the location where the seal pup was found,
            - `Tierart`: breed,
            - `Aktuell`: current status in {Reha, Ausgewildert, Verstorben} (English translation: {rehabilitation,
                released, deceased}),
            - `Erstellt_am`: date when the raw pdf file was created.

        Parameters
        ----------
        pdf_file
            A`BytesIO` object that describes a raw pdf file holding information about rescued seal pups.

        Returns
        -------
            A `pandas DataFrame` holding raw information about rescued seal pups.
        """
        pdf_reader = PdfReader(copy(pdf_file))
        num_pages_pdf = len(pdf_reader.pages)
        creation_date = pdf_reader.metadata.creation_date

        # Page 1: has a different format than the remaining pages, and, thus, needs a different `area` value
        df = tabula.read_pdf(
            copy(pdf_file),
            pages="1",
            encoding="cp1252",
            area=[10, 0, 95, 100],
            relative_area=True,
            multiple_tables=False,
            pandas_options={
                "header": None,
                "names": [
                    "Fundort",
                    "Einlieferungsdatum",
                    "Tierart",
                    "Aktuell",
                ],
            },
        )[0]

        # Remaining pages
        if num_pages_pdf > 1:
            df_page_2pp = tabula.read_pdf(
                copy(pdf_file),
                pages="2-" + str(num_pages_pdf),
                encoding="cp1252",
                area=[5, 0, 95, 100],
                relative_area=True,
                multiple_tables=False,
                pandas_options={
                    "header": None,
                    "names": [
                        "Fundort",
                        "Einlieferungsdatum",
                        "Tierart",
                        "Aktuell",
                    ],
                },
            )[0]
            df = pd.concat([df, df_page_2pp]).reset_index(drop=True)
        df["Erstellt_am"] = creation_date

        # Coerce columns with date values to datetime
        df = df.assign(
            Erstellt_am=pd.to_datetime(
                df["Erstellt_am"], format="%Y-%m-%d %H:%M:%S%z", utc=True
            ),
            Einlieferungsdatum=pd.to_datetime(
                df["Einlieferungsdatum"], format="%d.%m.%Y"
            ),
        )
        return df

    def clean_location_name(self, finding_place: str) -> Dict:
        """
        Returns the best match in `self.df_finding_places` for a given `location_name`.

        Parameters
        ----------
        finding_place
            Name of the location where a seal pup was found.

        Returns
        -------
        A dictionary with keys `raw_finding_place` and `suggested_finding_place`.
        """

        try:
            closest_match = difflib.get_close_matches(
                finding_place,
                list(self.dict_finding_place_corrections.keys()) + list(self.df_finding_places["Name"]),  # TODO drop NA
                n=1,
                cutoff=0.0
            )[0]
            try:
                suggested_finding_place = self.dict_finding_place_corrections[closest_match]
            except KeyError:
                suggested_finding_place = closest_match
        except TypeError as error:
            if np.isnan(finding_place):
                suggested_finding_place = "Unknown"
            else:
                print(error)
                raise

        return {
            "raw_finding_place": finding_place,
            "suggested_finding_place": suggested_finding_place
        }

    @staticmethod
    def _compute_hash(df_columns2hash: pd.DataFrame) -> pd.Series:
        """
        Computes the `sha256`- value for each row in `df_columns2hash`.

        Parameters
        ----------
        df_columns2hash
            A `pandas DataFrame`.

        Returns
        -------
        A `pandas Series` of hashed column values in `df_columns2hash`.
        """
        return df_columns2hash.apply(
            lambda row: sha256(row.to_string(index=False).encode("utf-8")).hexdigest(),
            axis=1,
        )

    def historicize_rob(self) -> pd.DataFrame:
        """
        Compares entries in `pandas Dataframes` `self.df_rob_cleaned` and `self.df_rob_historicized` and only returns
        values  of `self.df_rob_cleaned` that do not already exist in `self.df_rob_historicized`.

        Returns
        -------
        A `pandas Dataframe` that holds novel, cleaned input data about rescued seal pups.
        """
        df_rob_new = self.df_rob_cleaned.copy()
        df_rob_old = self.df_rob_historicized.copy()

        # Create system-id and system-hash value in `df_rob_new`:
        # Entries are identified by their values in `Fundort` (finding place), `Einlieferungsdatum` (admission date),
        # and `Tierart` (breed). Since there may exist multiple animals of the same finding place, admission date and
        # breed, the count of an animal within each group by `Erstellt_am` (creation date) is additionally used for
        # idenfification.
        df_rob_new["Sys_id"] = self._compute_hash(
            df_rob_new.assign(
                Count=(
                    df_rob_new.groupby(
                        [
                            "Fundort",
                            "Einlieferungsdatum",
                            "Tierart",
                            "Erstellt_am",
                        ]  # Group
                    ).cumcount()
                )
            )[
                ["Count", "Fundort", "Einlieferungsdatum", "Tierart"]
            ]  # Unique identifier
        )
        df_rob_new["Sys_hash"] = self._compute_hash(df_rob_new[["Sys_id", "Aktuell"]])

        # For each `Sys_hash`, keep only the entry with the earliest date in `Erstellt_am` in `df_rob_new`
        df_rob_new = (
            df_rob_new.sort_values(["Sys_hash", "Erstellt_am"])
            .groupby("Sys_hash")
            .first()
            .reset_index()
        )

        # Find entries that already exist in `df_rob_old` and that can be ignored in `df_rob_new`
        entry_exists = df_rob_new["Sys_hash"].isin(df_rob_old["Sys_hash"])
        if entry_exists.all():  # Abort historcization procedure if nothing has changed
            print(
                "No changes in `self.rob_raw with respect` to `self.df_rob_historicized`. Terminating update."
            )
            sys.exit(0)

        # Return entries that do not exist in `df_rob_old`
        return df_rob_new[~entry_exists].assign(
            Sys_aktualisiert_am=datetime.now(timezone.utc)
        )

    def update_rob(self) -> None:
        """
        Updates  `self.df_new_rob_historicized`. That is,
        1. Reads the raw PDF into a `pandas Dataframe`
        2. Corrects spelling mistakes in the names of finding places in the raw data and adds geo-coordinates
        3. Updates the catalogued finding places
        4. Saves the cleaned input data and catalogued finding places to the local file system

        Returns
        -------
        None
        """
        # Check for changes
        if len(self.changelogs) == 0:
            print("No changes new files exist. Terminating update.")
            sys.exit(0)

        # Read raw data from ByteIO object into pandas DataFrame
        df_rob_raw = pd.concat(
            [self.read_rob_raw(rob_raw) for rob_raw in self.rob_raw]
        ).reset_index(drop=True)

        raw_finding_places = df_rob_raw["Fundort"].unique()
        new_finding_places = [
            finding_place for finding_place in raw_finding_places
            if finding_place not in
               list(self.dict_finding_place_corrections.keys()) + list(self.df_finding_places["Name"])
        ]

        # Suggest spelling corrections for location names
        df_suggested_finding_places = pd.DataFrame(
            [self.clean_location_name(finding_place) for finding_place in new_finding_places]
        )

        # Join geo positions and show imprecise corrections for manual review
        df_corrected_finding_places = (
            pd.merge(
                df_suggested_finding_places,
                self.df_finding_places,
                left_on="suggested_finding_place", right_on="Name", how="left"
            )
            .drop(columns=["Name"])
            .rename(columns={
                "raw_finding_place": "Raw Finding Place",
                "suggested_finding_place": "Suggested Finding Place",
                "Lat": "Suggested Lat",
                "Long": "Suggested Long"
            })
            .sort_values(by="Suggested Finding Place")
            .reset_index(drop=True)
        )
        df_corrected_finding_places[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]] = None, None, None
        df_corrected_finding_places = df_corrected_finding_places[
            ["Raw Finding Place", "Suggested Finding Place", "Corrected Finding Place",
             "Suggested Lat", "Corrected Lat", "Suggested Long", "Corrected Long"]
        ]

        is_incorrect = (
            df_corrected_finding_places[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]]
            .isnull().values.any()
        )
        is_inconsistent = not (
            df_corrected_finding_places[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]]
            .drop_duplicates()["Corrected Finding Place"]
            .is_unique
        )
        while is_incorrect or is_inconsistent:
            df_corrected_finding_places = (
                show(df_corrected_finding_places)
                .get_dataframes("df_corrected_finding_places")
            )
            is_incorrect = (
                df_corrected_finding_places[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]]
                .isnull().values.any()
            )
            is_inconsistent = not (
                df_corrected_finding_places[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]]
                .drop_duplicates()["Corrected Finding Place"]
                .is_unique
            )
            if is_incorrect:
                print("""Some finding places are still uncorrected, please provide the missing values.""")
            if is_inconsistent:
                print(
                    """
                    Some finding places have inconsistent longitude and latitude values, please correct the provided 
                    coordinates.
                    """
                )

        # Store new finding place corrections
        dict_new_finding_place_corrections = self.dict_finding_place_corrections.copy()
        dict_new_finding_place_corrections.update(
            self._create_corrections_dict(
                df_corrected_finding_places.copy()
                [df_corrected_finding_places["Raw Finding Place"] !=
                 df_corrected_finding_places["Corrected Finding Place"]]
                [["Raw Finding Place", "Corrected Finding Place"]]
                .rename(columns={"Raw Finding Place": "Original", "Corrected Finding Place": "Correction"})
            )
        )
        self.dict_new_finding_place_corrections = dict_new_finding_place_corrections

        # Store new finding places
        self.df_new_finding_places = (
            pd.concat([
                df_corrected_finding_places.copy()[["Corrected Finding Place", "Corrected Lat", "Corrected Long"]]
                .rename(columns={"Corrected Finding Place": "Name", "Corrected Lat": "Lat", "Corrected Long": "Long"}),
                self.df_finding_places
            ], ignore_index=True)
            .drop_duplicates()
            .sort_values(by="Name")
        )

        # Correct finding places
        df_rob_cleaned = df_rob_raw.copy()
        df_rob_cleaned["Fundort"] = df_rob_raw["Fundort"].replace(to_replace=self.dict_new_finding_place_corrections)
        self.df_rob_cleaned = pd.merge(
            df_rob_cleaned, self.df_new_finding_places,
            how="left", left_on="Fundort", right_on="Name"
        )[["Fundort", "Lat", "Long", "Einlieferungsdatum", "Tierart", "Aktuell", "Erstellt_am"]]

        # Historicize the information in `self.df_rob_cleaned`
        self.df_new_rob_historicized = pd.concat(
            [self.df_rob_historicized, self.historicize_rob()], ignore_index=True
        ).sort_values(by=["Einlieferungsdatum", "Tierart", "Fundort", "Erstellt_am"])[
            [
                "Sys_id",
                "Fundort",
                "Lat",
                "Long",
                "Einlieferungsdatum",
                "Tierart",
                "Aktuell",
                "Erstellt_am",
                "Sys_aktualisiert_am",
                "Sys_hash",
            ]
        ]

        # Write `self.df_new_finding_places` and `self.df_new_rob_historicized` to storage
        # S3
        self._write_csv(
            self.df_new_finding_places,
            self.path_join.join(
                [self.path_to_interim_data, "catalogued_finding_places.csv"]
            ),
        )
        self._write_csv(
            pd.DataFrame({
                "Original": self.dict_new_finding_place_corrections.keys(),
                "Correction": self.dict_new_finding_place_corrections.values()
            }),
            self.path_join.join(
                [self.path_to_interim_data, "finding_place_corrections.csv"]
            ),
        )
        self._write_csv(
            self.df_new_rob_historicized,
            self.path_join.join([self.path_to_deployment_data, "rob.csv"]),
        )

        # local (for clearml versioning)
        self.df_new_finding_places.to_csv(
            os.path.join(PATH_TO_OUT, "catalogued_finding_places.csv"),
            index=False,
        )
        (
            pd.DataFrame({
                "Original": self.dict_new_finding_place_corrections.keys(),
                "Correction": self.dict_new_finding_place_corrections.values()
            })
            .sort_values(by="Correction")
            .to_csv(
                os.path.join(PATH_TO_OUT, "finding_place_corrections.csv"), index=False
            )
        )
        self.df_new_rob_historicized.to_csv(
            os.path.join(PATH_TO_OUT, "rob.csv"), index=False
        )

        # Update changelogs
        for changelog in self.changelogs:
            self._delete_changelog(changelog)

    @staticmethod
    @abstractmethod
    def _write_csv(df: pd.DataFrame, path_to_csv: str) -> None:
        """
        Writes the given `pandas DataFrame`, `df`, as a comma-separated-values (csv) file into the location specified
        in `path_to_csv`. If the file does not exist, yet, it is created. Otherwise, it is overwritten.

        Parameters
        ----------
        df
            A `pandas DataFrame`.

        path_to_csv
            A path to a csv file.

        Returns
        -------
        None
        """
        raise NotImplementedError


class RobHistoricizerAWS(RobHistoricizer):
    def __init__(self):
        """
        Initializes an instance of class `RobHistoricizerAWS`. That is, sets up all pre-requisites to access and write
        to the S3-bucket (https://s3.console.aws.amazon.com/s3/buckets/rob-oliver) and historicize data about rescued
        seal pups of the Seehundstation Friedrichskoog.
        """
        # AWS credentials
        aws_access_key_id, aws_secret_access_key = self._get_aws_login()
        # AWS client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        # S3 bucket
        self.s3_bucket = "rob-oliver"
        # S3 folder paths and path join
        super().__init__(
            path_to_raw_data="data/raw",
            path_to_changelogs="data/changelog",
            path_to_interim_data="data/interim",
            path_to_deployment_data="data/deployment",
            path_join="/",
        )

    @staticmethod
    def _get_aws_login() -> Tuple[str, str]:
        """
        Gets the AWS-login-credentials from the environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`.

        Returns
        -------
        Values stored in environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
        """
        return os.getenv("AWS_ACCESS_KEY_ID"), os.getenv("AWS_SECRET_ACCESS_KEY")

    def _get_changelogs(self) -> List[str]:
        changelogs = self.s3_client.list_objects_v2(
            Bucket=self.s3_bucket, Prefix=self.path_to_changelogs
        )["Contents"]
        return [
            os.path.basename(changelog["Key"])
            for changelog in changelogs
            if os.path.basename(changelog["Key"]) != ""
        ]

    def _delete_changelog(self, changelog_name: str) -> None:
        self.s3_client.delete_object(
            Bucket=self.s3_bucket,
            Key=self.path_join.join([self.path_to_changelogs, changelog_name]),
        )

    def _read_csv(self, path_to_csv: str) -> pd.DataFrame:
        csv = self.s3_client.get_object(Bucket=self.s3_bucket, Key=path_to_csv)["Body"]
        return pd.read_csv(csv)

    def _get_rob_raw(self, changelog_name) -> io.BytesIO:
        try:
            return io.BytesIO(
                self.s3_client.get_object(
                    Bucket=self.s3_bucket,
                    Key=self.path_join.join(
                        [self.path_to_raw_data, changelog_name[:-3] + "pdf"]
                    ),
                )["Body"].read()
            )
        except botocore.exceptions.ClientError as error:
            print(error)
            raise
        except:
            print("An unexpected exception has occurred.")
            raise

    def _write_csv(self, df: pd.DataFrame, path_to_csv: str) -> None:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        self.s3_client.put_object(
            Body=csv_buffer.getvalue(), Bucket=self.s3_bucket, Key=path_to_csv
        )

    @staticmethod
    def _add_to_clearml_dataset() -> None:
        """
        Adds the dataset historicized in `self.update_rob` to a clearml dataset
        (https://clear.ml/docs/latest/docs/references/sdk/dataset/). Clearml datasets are tracked by version, i.e., we
        can restore previous versions of the dataset.

        Returns
        -------
        None
        """

        dataset = Dataset.create(
            dataset_name=DATASET_NAME,
            dataset_project=PROJECT_NAME,
            parent_datasets=[
                Dataset.get(dataset_project=PROJECT_NAME, dataset_name=DATASET_NAME).id
            ],
        )

        # Sync local folder
        dataset.sync_folder(local_path=os.path.join(PATH_TO_OUT))

        # Finalize and upload the data
        dataset.finalize(auto_upload=True)

    def update_rob(self) -> None:
        """
        Updates  `self.df_new_rob_historicized`. That is,
        1. Reads the raw PDF into a `pandas Dataframe`
        2. Corrects spelling mistakes in the names of finding places in the raw data and adds geo-coordinates
        3. Updates the catalogued finding places
        4. Saves the cleaned input data and catalogued finding places to the local file system
        5. Creates a new version of the cleaned input data and catalogued finding places on clear-ml (https://clear.ml/)

        Returns
        -------
        None
        """
        super().update_rob()

        # Version `df_new_finding_places` and `df_new_rob_historicized` in a clearml (https://clear.ml/) dataset
        self._add_to_clearml_dataset()


class RobHistoricizerLocal(RobHistoricizer):
    def __init__(self):
        """
        Initializes an instance of class `RobHistoricizerLocal`. This class may be used to test the functionality of
        the parent class `RobHistoricizer` locally.
        """
        # Local paths to data
        path_to_raw_data = os.path.join("..", "data", "local", "raw")
        path_to_changelogs = os.path.join("..", "data", "local", "changelog")
        path_to_interim_data = os.path.join("..", "data", "local", "interim")
        path_to_deployment_data = os.path.join("..", "data", "local", "deployment")

        # Create local paths if they don't exist, yet
        local_paths = [
            path_to_raw_data,
            path_to_changelogs,
            path_to_interim_data,
            path_to_deployment_data,
        ]
        for path in local_paths:
            if not os.path.exists(path):
                os.makedirs(path)
                print(f"The directory {path} was created.")

        # Download data from S3 bucket (https://s3.console.aws.amazon.com/s3/buckets/rob-oliver)
        # Get s3 client
        config = botocore.client.Config(signature_version=botocore.UNSIGNED)
        s3 = boto3.client("s3", config=config)
        # List all files in s3 bucket
        s3_bucket = "rob-oliver"
        s3_bucket_list = s3.list_objects(Bucket=s3_bucket)["Contents"]
        s3_file_keys = [
            s3_obj_meta["Key"]
            for s3_obj_meta in s3_bucket_list
            if "." in s3_obj_meta["Key"]
        ]
        # Retrieve files and save to local file system
        for s3_key in s3_file_keys:
            # Retrieve file
            s3_obj = s3.get_object(Bucket=s3_bucket, Key=s3_key)
            # Set local path based on `s3_key`
            if "raw" in s3_key:
                path = path_to_raw_data
            elif "changelog" in s3_key:
                path = path_to_changelogs
            elif "interim" in s3_key:
                path = path_to_interim_data
            elif "deployment" in s3_key:
                path = path_to_deployment_data
            else:
                raise ValueError(
                    f"Cannot find designated local file path for S3 bucket key {s3_key}."
                )
            # Write file to local file system
            file_name = os.path.basename(s3_key)
            with open(os.path.join(path, file_name), "wb") as binary_file:
                binary_file.write(io.BytesIO(s3_obj["Body"].read()).read())

        # Call parent init
        super().__init__(
            path_to_raw_data=path_to_raw_data,
            path_to_changelogs=path_to_changelogs,
            path_to_interim_data=path_to_interim_data,
            path_to_deployment_data=path_to_deployment_data,
            path_join=os.path.sep,
        )

    def _get_changelogs(self) -> List[str]:
        absolute_changelogs = glob.glob(os.path.join(self.path_to_changelogs, "*"))
        return [os.path.basename(changelog) for changelog in absolute_changelogs]

    def _delete_changelog(self, changelog_name: str) -> None:
        try:
            os.remove(os.path.join(self.path_to_changelogs, changelog_name))
        except FileNotFoundError as error:
            print(error)
        except:
            print("An unexpected error has occurred.")
            raise

    def _get_rob_raw(self, changelog_name: str) -> io.BytesIO:
        with open(
            os.path.join(self.path_to_raw_data, changelog_name[:-3] + "pdf"), "rb"
        ) as binary_file:
            rob_raw = io.BytesIO(binary_file.read())
        return rob_raw

    def _read_csv(self, path_to_csv: str) -> pd.DataFrame:
        return pd.read_csv(path_to_csv)

    @staticmethod
    def _write_csv(df: pd.DataFrame, path_to_csv: str) -> None:
        df.to_csv(path_to_csv, index=False)


if __name__ == "__main__":
    historicizer_class: Literal["aws", "local"] = "aws"

    if historicizer_class == "aws":
        rob_historicizer = RobHistoricizerAWS()
    elif historicizer_class == "local":
        rob_historicizer = RobHistoricizerLocal()
    else:
        raise ValueError(
            f"Invalid `historicizer_class` {historicizer_class}. Choose in `['aws', 'local']`."
        )
    rob_historicizer.update_rob()
