import pandas as pd
import boto3
import io
import os
import botocore
from abc import ABC, abstractmethod
from typing import List, Tuple


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
        The abstract base class to historicise information about seal pups rescued by the Seehundstation Friedrichskoog.

        Parameters
        ----------
        path_to_raw_data
            File path to the raw data, i.e., the folder that contains pdf files saved from
            'https://www.seehundstation-friedrichskoog.de/wp-content/heuler/1.6HomepageHeuler.pdf' at different points
            in time
        path_to_changelogs
            File path to the changelog files. In their file names, these indicate which raw pdf files have not been
            historicised, yet.
        path_to_interim_data

        path_to_deployment_data
        path_join
        """
        self.path_to_raw_data = path_to_raw_data
        self.path_to_changelogs = path_to_changelogs
        self.path_to_interim_data = path_to_interim_data
        self.path_to_deployment_data = path_to_deployment_data
        self.path_join = path_join

        self.df_finding_places = self._read_csv(
            path_join.join([path_to_interim_data, "catalogued_finding_places.csv"])
        )
        self.df_rob_historicized = self._read_csv(
            path_join.join([path_to_deployment_data, "rob.csv"])
        )
        self.changelogs = self._get_changelogs()
        self.rob_raw = [self._get_rob_raw(changelog) for changelog in self.changelogs]

    @abstractmethod
    def _get_changelogs(self) -> List[str]:
        """
        Gets the names of changelog files in `self.path_to_changelogs`. A changelog-file is named in the pattern
        yyyymmdd_1.6HomepageHeuler.log. For each changelog file in `path_to_changelogs` there exists a pdf file
        yyyymmdd_1.6HomepageHeuler.pdf in `self.path_to_raw` that has not been historicised, yet.

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


class RobHistoricizerAWS(RobHistoricizer):
    def __init__(self, local=False):
        """

        Parameters
        ----------
        local
        """
        aws_access_key_id = None
        aws_secret_access_key = None
        if local:
            aws_access_key_id, aws_secret_access_key = self._get_aws_login()
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
        )
        self.s3_bucket = "rob-oliver"
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
        return pd.read_csv(self.path_join.join(["s3:/", self.s3_bucket, path_to_csv]))

    def _get_rob_raw(self, changelog) -> io.BytesIO:
        try:
            return io.BytesIO(
                self.s3_client.get_object(
                    Bucket=self.s3_bucket,
                    Key=self.path_join.join(
                        [self.path_to_raw_data, changelog[:-3] + "pdf"]
                    ),
                )["Body"].read()
            )
        except botocore.exceptions.ClientError as error:
            print(error)
            raise
        except:
            print("An unexpected exception has occured.")
            raise


if __name__ == "__main__":
    rob_historiciser_aws = RobHistoricizerAWS(local=True)
    print(":-D")
