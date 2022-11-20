import json
import os
from json import JSONDecodeError
from pathlib import Path

import google.auth
import jsonschema
from dateutil import tz
from google.auth.exceptions import DefaultCredentialsError

from elementary.exceptions.exceptions import (
    NoElementaryProfileError,
    NoProfilesFileError,
    InvalidArgumentsError,
)
from elementary.utils.ordered_yaml import OrderedYaml


class Config:
    _SLACK = "slack"
    _AWS = "aws"
    _GOOGLE = "google"
    _CONFIG_FILE_NAME = "config.yml"

    DEFAULT_CONFIG_DIR = str(Path.home() / ".edr")
    DEFAULT_PROFILES_DIR = str(Path.home() / ".dbt")

    DBT_TRACKING_JSON_SCHEMA = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "type": "object",
        "properties": {
            key: {"type": ["boolean", "null"]}
            for key in ["database", "schema", "identifier"]
        },
        "additionalProperties": False,
    }

    def __init__(
        self,
        config_dir: str = DEFAULT_CONFIG_DIR,
        profiles_dir: str = DEFAULT_PROFILES_DIR,
        profile_target: str = None,
        dbt_quoting: bool = None,
        update_bucket_website: bool = None,
        slack_webhook: str = None,
        slack_token: str = None,
        slack_channel_name: str = None,
        timezone: str = None,
        aws_profile_name: str = None,
        aws_access_key_id: str = None,
        aws_secret_access_key: str = None,
        s3_bucket_name: str = None,
        google_project_name: str = None,
        google_service_account_path: str = None,
        gcs_bucket_name: str = None,
    ):
        self.config_dir = config_dir
        self.profiles_dir = profiles_dir
        self.profile_target = profile_target
        self.dbt_quoting = self._parse_dbt_quoting(dbt_quoting)

        config = self._load_configuration()

        self.target_dir = self._first_not_none(
            config.get("target-path"),
            os.getcwd(),
        )

        self.update_bucket_website = self._first_not_none(
            update_bucket_website,
            config.get("update_bucket_website"),
            False,
        )

        self.timezone = self._first_not_none(
            timezone,
            config.get("timezone"),
        )

        slack_config = config.get(self._SLACK, {})
        self.slack_webhook = self._first_not_none(
            slack_webhook,
            slack_config.get("notification_webhook"),
        )
        self.slack_token = self._first_not_none(
            slack_token,
            slack_config.get("token"),
        )
        self.slack_channel_name = self._first_not_none(
            slack_channel_name,
            slack_config.get("channel_name"),
        )
        self.is_slack_workflow = self._first_not_none(
            slack_config.get("workflows"),
            False,
        )

        aws_config = config.get(self._AWS, {})
        self.aws_profile_name = self._first_not_none(
            aws_profile_name,
            aws_config.get("profile_name"),
        )
        self.s3_bucket_name = self._first_not_none(
            s3_bucket_name, aws_config.get("s3_bucket_name")
        )
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key

        google_config = config.get(self._GOOGLE, {})
        self.google_project_name = self._first_not_none(
            google_project_name,
            google_config.get("project_name"),
        )
        self.google_service_account_path = self._first_not_none(
            google_service_account_path,
            google_config.get("service_account_path"),
        )
        self.gcs_bucket_name = self._first_not_none(
            gcs_bucket_name,
            google_config.get("gcs_bucket_name"),
        )

        self.anonymous_tracking_enabled = config.get("anonymous_usage_tracking", True)

    def _load_configuration(self) -> dict:
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        config_file_path = os.path.join(self.config_dir, self._CONFIG_FILE_NAME)
        if not os.path.exists(config_file_path):
            return {}
        return OrderedYaml().load(config_file_path) or {}

    @property
    def has_send_report_platform(self):
        return (
            (self.slack_token and self.slack_channel_name)
            or self.has_s3
            or self.has_gcs
        )

    @property
    def has_slack(self) -> bool:
        return self.slack_webhook or (self.slack_token and self.slack_channel_name)

    @property
    def has_s3(self):
        return self.s3_bucket_name

    @property
    def has_gcloud(self):
        if self.google_service_account_path:
            return True
        try:
            google.auth.default()
            return True
        except DefaultCredentialsError:
            return False

    @property
    def has_gcs(self):
        return self.gcs_bucket_name and self.has_gcloud

    def validate_monitor(self):
        self._validate_elementary_profile()
        self._validate_timezone()
        if not self.has_slack:
            raise InvalidArgumentsError(
                "Either a Slack token and a channel or a Slack webhook is required."
            )

    def validate_report(self):
        self._validate_elementary_profile()

    def validate_send_report(self):
        self._validate_elementary_profile()
        if not self.has_send_report_platform:
            raise InvalidArgumentsError(
                "You must provide a platform to upload the report to (Slack token / S3 / GCS)."
            )

    def _validate_elementary_profile(self):
        profiles_path = os.path.join(self.profiles_dir, "profiles.yml")
        try:
            profiles_yml = OrderedYaml().load(profiles_path)
            if "elementary" not in profiles_yml:
                raise NoElementaryProfileError
        except FileNotFoundError:
            raise NoProfilesFileError(self.profiles_dir)

    def _validate_timezone(self):
        if self.timezone and not tz.gettz(self.timezone):
            raise InvalidArgumentsError("An invalid timezone was provided.")

    @staticmethod
    def _first_not_none(*values):
        return next((v for v in values if v is not None), None)

    @classmethod
    def _parse_dbt_quoting(cls, dbt_quoting):
        if dbt_quoting is None:
            return None

        dbt_quoting = dbt_quoting.strip()
        if dbt_quoting == "all":
            return {"database": True, "schema": True, "identifier": True}
        elif dbt_quoting == "none":
            return {"database": False, "schema": False, "identifier": False}
        else:
            try:
                parsed_dbt_quoting = json.loads(dbt_quoting)
                jsonschema.validate(parsed_dbt_quoting, cls.DBT_TRACKING_JSON_SCHEMA)

                full_dbt_quoting = {
                    "database": None,
                    "schema": None,
                    "identifier": None,
                }
                full_dbt_quoting.update(parsed_dbt_quoting)
                return full_dbt_quoting
            except json.JSONDecodeError:
                raise InvalidArgumentsError(
                    "An invalid JSON was passed for argument dbt_quoting"
                )
            except jsonschema.exceptions.ValidationError:
                raise InvalidArgumentsError(
                    "The supplied parameter dbt_quoting is a valid JSON but has an incorrect "
                    "format"
                )
