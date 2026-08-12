import click

w, h = click.get_terminal_size()
args = click.get_os_args()
click.echo("hello")

@click.option("--n", default=1)
def cli(n):
    pass
