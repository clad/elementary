import click

from elementary.config.config import Config
from elementary.operations.upload_source_freshness import UploadSourceFreshnessOperation
from elementary.tracking.anonymous_tracking import AnonymousTracking

_MODULE_NAME = "run-operation"


@click.group()
def run_operation():
    """
    Utilities for Elementary operations.
    """
    pass


@run_operation.command()
@click.option(
    "--project-dir",
    type=click.Path(exists=True),
    default=None,
    help="Which directory to look in for the dbt_project.yml file. Default is the current working directory.",
)
@click.option(
    "--profile-target",
    "-t",
    type=str,
    default=None,
    help="Which target to load for the given profile. "
    "If specified, the target will be used for both the 'elementary' profile and your dbt project."
    "Else, the default target will be used.",
)
@click.option(
    "--profiles-dir",
    "-p",
    type=click.Path(exists=True),
    default=None,
    help="Which directory to look in for the profiles.yml file. "
    "If not set, edr will look in the current working directory first, then HOME/.dbt/",
)
@click.pass_context
def upload_source_freshness(ctx, **conf):
    """
    Upload the results of `dbt source freshness` to Elementary's schema.
    This is required in order to monitor and get alerts on source freshness failures.
    """
    config = Config(**conf)
    anonymous_tracking = AnonymousTracking(config)
    anonymous_tracking.track_cli_start(_MODULE_NAME, None, ctx.command.name)
    UploadSourceFreshnessOperation(config).run()
    anonymous_tracking.track_cli_end(_MODULE_NAME, None, ctx.command.name)
