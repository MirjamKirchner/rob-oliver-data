import pandas as pd
import boto3
import io
import os
import botocore
import tabula
import difflib
import numpy as np
import inspect
import sys
import glob
from copy import copy
from abc import ABC, abstractmethod
from typing import List, Tuple
from PyPDF2 import PdfFileReader
from datetime import datetime, timezone
from typing import Dict
from pandasgui.gui import PandasGui
from PyQt5 import QtGui
from IPython.core.magic import register_line_magic
from operator import itemgetter
from hashlib import sha256
from clearml import Dataset

PROJECT_NAME = "rob-oliver"
DATASET_NAME = "rob"
PATH_TO_OUT = "../data/out"


class RobGui(PandasGui):
    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        """
        Saves the manual changes of the given `pandas DataFrame` to the instance of `RobGui`. This allows for manual
        corrections of suggested names and geo coordinates of finding places.

        Parameters
        ----------
        e
            A `QtGui.QCloseEvent`.

        Returns
        -------
        None
        """
        df_rob_cleaned = self.get_dataframes()["df_rob_cleaned"]

        # Save distinct finding places
        df_new_finding_places = (
            df_rob_cleaned.copy()[
                ["suggested_finding_place", "suggested_lat", "suggested_long"]
            ]
            .drop_duplicates()
            .rename(
                columns={
                    "suggested_finding_place": "Name",
                    "suggested_lat": "Lat",
                    "suggested_long": "Long",
                }
            )
        )
        self.store.add_dataframe(df_new_finding_places, "df_new_finding_places")

        # Reformat and save df_rob_cleaned
        df_rob_manually_corrected = (
            df_rob_cleaned.copy()
            .drop(columns=["raw_finding_place"])
            .rename(
                columns={
                    "suggested_finding_place": "Fundort",
                    "suggested_lat": "Lat",
                    "suggested_long": "Long",
                }
            )
        )
        self.store.add_dataframe(df_rob_manually_corrected, "df_rob_manually_corrected")

        # Call parent-class function
        super().closeEvent(e)


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
        """
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
        df_rob_historicized = self._read_csv(
            path_join.join([path_to_deployment_data, "rob.csv"])
        ).astype(
            {
                "Long": "float64",
                "Lat": "float64",
                "Einlieferungsdatum": "datetime64[ns]",
            }
        )
        self.df_rob_historicized = df_rob_historicized.assign(
            Erstellt_am=pd.to_datetime(
                df_rob_historicized["Erstellt_am"],
                format="%Y-%m-%d %H:%M:%S%z",
                utc=True,
            ),
            Sys_aktualisiert_am=pd.to_datetime(
                df_rob_historicized["Sys_aktualisiert_am"],
                format="%Y-%m-%d %H:%M:%S%z",
                utc=True,
            ),
        )

        # Interim and new data (to be filled during processing)
        self.df_rob_cleaned = None
        self.df_new_rob_historicized = None
        self.df_new_finding_places = None

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
        pdf_file_reader = PdfFileReader(copy(pdf_file))
        num_pages_pdf = pdf_file_reader.numPages
        creation_date = pdf_file_reader.documentInfo["/ModDate"]
        creation_date = datetime.strptime(
            creation_date.replace("'", ""), "D:%Y%m%d%H%M%S%z"
        )

        # Page 1: has a different format than the remaining pages, and needs, thus, a different `area` value
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
        A dictionary with keys `raw_finding_place`, `suggested_finding_place`, `suggested_long`, and `suggested_lat`.
        """
        try:
            suggested_finding_place = difflib.get_close_matches(
                finding_place, self.df_finding_places["Name"], n=1, cutoff=0.0
            )[0]
        except TypeError as error:
            if np.isnan(finding_place):
                suggested_finding_place = "Unknown"
            else:
                print(error)
                raise
        lat, long = self.df_finding_places.loc[
            self.df_finding_places["Name"] == suggested_finding_place, ["Lat", "Long"]
        ].to_numpy()[0]

        return {
            "raw_finding_place": finding_place,
            "suggested_finding_place": suggested_finding_place,
            "suggested_long": float(long),
            "suggested_lat": float(lat),
        }

    @staticmethod
    def _show_rob_cleaned(df_rob_cleaned: pd.DataFrame) -> PandasGui:
        """
        Shows `df_rob_cleaned` in a `PandasGui` and allows for manual correction. The corrected data frame is saved as
        an attribute of the `PandasGui` instance.

        Returns
        -------
        An instance of class `PandasGui`.
        """
        # TODO refactor so that only unique location mappings are shown
        rob_gui = RobGui(
            df_rob_cleaned=df_rob_cleaned.sort_values(
                by=["Erstellt_am", "Einlieferungsdatum"], ascending=False
            )
        )
        rob_gui.caller_stack = inspect.currentframe().f_back

        # Register IPython magic
        try:

            @register_line_magic
            def pg(line):
                rob_gui.store.eval_magic(line)
                return line

        except Exception as e:
            # Let this silently fail if no IPython console exists
            if (
                e.args[0]
                == "Decorator can only run in context where `get_ipython` exists"
            ):
                pass
            else:
                raise e

        return rob_gui

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

        # Suggest spelling corrections for location names and provide geo coordinates
        df_location_names_cleaned = pd.concat(
            [
                pd.DataFrame(
                    data=self.clean_location_name(location_name), index=[index]
                )
                for index, location_name in df_rob_raw["Fundort"].items()
            ]
        )

        # Join information and show for manual correction
        df_rob_cleaned = df_location_names_cleaned.join(
            df_rob_raw.drop(columns=["Fundort"])
        )

        self.df_rob_cleaned, df_new_finding_places = itemgetter(
            "df_rob_manually_corrected", "df_new_finding_places"
        )(self._show_rob_cleaned(df_rob_cleaned).get_dataframes())

        # Historicize the information in `self.df_rob_cleaned`
        df_new_rob_historicized = self.historicize_rob()

        # Save `df_new_finding_places` and `df_new_rob_historicized`
        self.df_new_finding_places = (
            pd.concat(
                [self.df_finding_places, df_new_finding_places], ignore_index=True
            )
            .drop_duplicates()
            .sort_values(by="Name")[["Name", "Lat", "Long"]]
        )
        self.df_new_rob_historicized = pd.concat(
            [self.df_rob_historicized, df_new_rob_historicized], ignore_index=True
        ).sort_values(by=["Einlieferungsdatum", "Tierart", "Fundort"])[
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
            self.df_new_rob_historicized,
            self.path_join.join([self.path_to_deployment_data, "rob.csv"]),
        )
        # local (for clearml versioning)
        self.df_new_finding_places.to_csv(
            os.path.join(PATH_TO_OUT, "catalogued_finding_places.csv"),
            index=False,
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
        4. Creates a new version of the cleaned input data and catalogued finding places on clear-ml (https://clear.ml/)

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
        df.to_csv(path_to_csv)


if __name__ == "__main__":
    historicizer_class = ["aws", "local"][0]
    if historicizer_class == "aws":
        rob_historicizer = RobHistoricizerAWS()
    elif historicizer_class == "local":
        rob_historicizer = RobHistoricizerLocal()
    else:
        raise ValueError(
            f"Invalid `historicizer_class` {historicizer_class}. Choose in `['aws', 'local']`."
        )
    rob_historicizer.update_rob()
