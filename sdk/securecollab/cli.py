# SPDX-License-Identifier: Apache-2.0
"""Click CLI entry point. Install with: pip install ./sdk then securecollab --help."""
import click


@click.group()
@click.option("--api-url", default="http://localhost:8000", envvar="SECURECOLLAB_API_URL", help="API base URL")
@click.pass_context
def cli(ctx, api_url):
    """SecureCollab SDK — local encryption and multi-party study workflow."""
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url


@cli.command()
@click.option("--csv", "csv_path", required=True, type=click.Path(exists=True), help="Path to CSV file")
@click.option("--study-id", required=True, help="Study ID")
@click.option("--email", "institution_email", required=True, help="Institution email")
@click.option("--dataset-name", default="", help="Dataset name")
@click.pass_context
def upload(ctx, csv_path, study_id, institution_email, dataset_name):
    """Encrypt CSV and upload to a study. Use backend/sdk.py for full implementation."""
    click.echo(f"Upload: csv={csv_path} study_id={study_id} email={institution_email}", err=True)
    click.echo("Full implementation: run backend/sdk.py or use SecureCollabClient from this package.", err=True)


@cli.command()
def generate_key_share():
    """Generate a new secret key share (stored locally, password-protected)."""
    click.echo("Use backend/sdk.py generate-key-share for full implementation.", err=True)


@cli.command()
@click.argument("study_id")
@click.option("--email", required=True, help="Institution email")
def verify_audit(study_id, email):
    """Verify local audit log against server trail."""
    click.echo(f"Verify audit: study_id={study_id} email={email}", err=True)
    click.echo("Use backend/sdk.py verify-audit for full implementation.", err=True)


def main():
    """Entry point for console_scripts."""
    cli(obj={})


if __name__ == "__main__":
    main()
