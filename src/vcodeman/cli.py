"""Click-based CLI for vcodeman."""

import json
import os
import sys
from pathlib import Path

import click

from vcodeman import __version__
from vcodeman.parser import FilelistParser
from vcodeman.resolver import CircularReferenceError, UndefinedVariableError


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
@click.option('-v', '--verbose', count=True, help='Increase verbosity (-v, -vv, -vvv)')
@click.option('-q', '--quiet', is_flag=True, help='Suppress non-error output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Verilog-XL Filelist Parser and Flattener.

    Parse nested filelists and output a flattened result with:
    - All nested filelists resolved and merged
    - Environment variables expanded
    - Relative paths resolved to absolute paths
    - All options preserved (-y, -v, +incdir+, +define+, +libext+)
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet


@cli.command()
@click.argument('filelist', type=click.Path(exists=True, readable=True, path_type=Path))
@click.option(
    '-o', '--output',
    type=click.Path(path_type=Path),
    help='Output file path (default: stdout)'
)
@click.option(
    '-f', '--format',
    type=click.Choice(['text', 'json', 'sqlite'], case_sensitive=False),
    default='text',
    help='Output format: text (flattened filelist), json (structured data), or sqlite (database file)'
)
@click.option(
    '--strict-env',
    is_flag=True,
    help='Fail on undefined environment variables'
)
@click.option(
    '--env',
    'env_pairs',
    multiple=True,
    metavar='KEY=VALUE',
    help='Inject KEY=VALUE into the environment before parsing. Repeatable. '
    'Lets the caller set the variables a filelist references via $VAR / ${VAR} '
    'without polluting the surrounding shell. Example: --env PROJ=myproj '
    '--env USERDIR=alice.'
)
@click.pass_context
def parse(ctx, filelist, output, format, strict_env, env_pairs):
    """Parse and flatten a Verilog-XL filelist.

    Resolves all nested filelists (-f/-F), expands environment variables,
    and outputs a flattened filelist that can be used directly with simulators.

    Examples:
        vcodeman parse design.f                    # Output to stdout
        vcodeman parse design.f -o flat.f          # Output to file
        vcodeman parse design.f --format json      # JSON output for debugging
        vcodeman parse design.f --env PROJ=foo --env USR=alice
    """
    verbose = ctx.obj.get('verbose', 0)
    quiet = ctx.obj.get('quiet', False)

    if not quiet and verbose > 0:
        click.echo(f"Parsing: {filelist}", err=True)

    # Inject any --env KEY=VALUE pairs before the parser starts expanding
    # env vars. Validate format up front; bad input dies with a clear error.
    for pair in env_pairs:
        if '=' not in pair:
            click.secho(
                f"Error: --env value must be KEY=VALUE (got: {pair!r})",
                fg='red', err=True,
            )
            sys.exit(2)
        key, _, value = pair.partition('=')
        if not key:
            click.secho(
                f"Error: --env KEY may not be empty (got: {pair!r})",
                fg='red', err=True,
            )
            sys.exit(2)
        os.environ[key] = value

    try:
        # Create parser
        parser = FilelistParser(strict_env_vars=strict_env)

        # Parse filelist
        result = parser.parse(filelist_path=filelist)

        # Generate output based on format
        if format == 'json':
            output_data = _format_json(result)
            # Write output
            if output:
                output.write_text(output_data)
                if not quiet:
                    click.echo(f"Output written to: {output}", err=True)
            else:
                click.echo(output_data)
        elif format == 'sqlite':
            # SQLite format requires output file
            if not output:
                output = Path(filelist).with_suffix('.db')
            _export_sqlite(result, output)
            if not quiet:
                click.echo(f"SQLite database written to: {output}", err=True)
        else:  # text - flattened filelist
            output_data = _format_flattened(result)
            # Write output
            if output:
                output.write_text(output_data)
                if not quiet:
                    click.echo(f"Output written to: {output}", err=True)
            else:
                click.echo(output_data)

        if not quiet and verbose > 0:
            click.echo(f"Parse completed successfully", err=True)

    except CircularReferenceError as e:
        click.secho(f"Error: Circular reference detected", fg='red', err=True)
        click.echo(f"  {str(e)}", err=True)
        sys.exit(1)
    except UndefinedVariableError as e:
        click.secho(f"Error: Undefined environment variable", fg='red', err=True)
        click.echo(f"  {str(e)}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.secho(f"Error: File not found", fg='red', err=True)
        click.echo(f"  {str(e)}", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho(f"Error: Parse failed", fg='red', err=True)
        click.echo(f"  {str(e)}", err=True)
        if verbose > 1:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _format_json(result) -> str:
    """Format ParsedFilelist as JSON."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def _export_sqlite(result, output_path: Path) -> None:
    """Export parsed data to a SQLite file.

    Args:
        result: ParsedFilelist instance with parsed data
        output_path: Path to write the SQLite database file
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from vcodeman.models import (
        Base, Filelist, FileEntry, LibraryDirectory, LibraryFile,
        IncludeDirectory, MacroDefinition, LibraryExtension, LineItem, ParsedFilelist
    )

    # Remove existing file if it exists
    if output_path.exists():
        output_path.unlink()

    # Create file-based engine
    file_engine = create_engine(f"sqlite:///{output_path}")
    Base.metadata.create_all(file_engine)
    SessionLocal = sessionmaker(bind=file_engine)
    session = SessionLocal()

    try:
        parsed_data = result._parsed_data
        if not parsed_data:
            return

        # Create ParsedFilelist entry
        parsed_filelist = ParsedFilelist(
            root_filepath=result.root_filepath,
            timestamp=result.timestamp,
            warnings=result.warnings,
            errors=result.errors
        )
        session.add(parsed_filelist)
        session.flush()

        # Map old filelist IDs to new ones
        filelist_id_map = {}

        # Insert filelists
        for fl_data in parsed_data.get('filelists', []):
            filelist = Filelist(
                filepath=fl_data['filepath'],
                parent_id=filelist_id_map.get(fl_data.get('parent_id')),
                line_number=fl_data.get('line_number'),
                nesting_level=fl_data.get('nesting_level', 0),
                exists=fl_data.get('exists', True)
            )
            session.add(filelist)
            session.flush()
            filelist_id_map[fl_data['id']] = filelist.id

            # Insert line items for this filelist
            for li_data in fl_data.get('line_items', []):
                line_item = LineItem(
                    filelist_id=filelist.id,
                    line_number=li_data['line_number'],
                    item_type=li_data['item_type'],
                    original_text=li_data['original_text'],
                    resolved_text=li_data.get('resolved_text'),
                    include_path=li_data.get('include_path')
                )
                session.add(line_item)

        # Insert file entries
        for fe_data in parsed_data.get('file_entries', []):
            file_entry = FileEntry(
                filelist_id=filelist_id_map.get(fe_data['filelist_id'], fe_data['filelist_id']),
                filepath=fe_data['filepath'],
                original_path=fe_data['original_path'],
                line_number=fe_data['line_number'],
                exists=fe_data.get('exists', True),
                is_library=fe_data.get('is_library', False)
            )
            session.add(file_entry)

        # Insert library directories
        for ld_data in parsed_data.get('library_directories', []):
            lib_dir = LibraryDirectory(
                filelist_id=filelist_id_map.get(ld_data['filelist_id'], ld_data['filelist_id']),
                dirpath=ld_data['dirpath'],
                original_path=ld_data['original_path'],
                line_number=ld_data['line_number'],
                exists=ld_data.get('exists', True)
            )
            session.add(lib_dir)

        # Insert library files
        for lf_data in parsed_data.get('library_files', []):
            lib_file = LibraryFile(
                filelist_id=filelist_id_map.get(lf_data['filelist_id'], lf_data['filelist_id']),
                filepath=lf_data['filepath'],
                original_path=lf_data['original_path'],
                line_number=lf_data['line_number'],
                exists=lf_data.get('exists', True)
            )
            session.add(lib_file)

        # Insert include directories
        for id_data in parsed_data.get('include_directories', []):
            inc_dir = IncludeDirectory(
                filelist_id=filelist_id_map.get(id_data['filelist_id'], id_data['filelist_id']),
                dirpath=id_data['dirpath'],
                original_path=id_data['original_path'],
                line_number=id_data['line_number'],
                position=id_data.get('position', 0),
                exists=id_data.get('exists', True)
            )
            session.add(inc_dir)

        # Insert macro definitions
        for md_data in parsed_data.get('macro_definitions', []):
            macro_def = MacroDefinition(
                filelist_id=filelist_id_map.get(md_data['filelist_id'], md_data['filelist_id']),
                name=md_data['name'],
                value=md_data.get('value'),
                line_number=md_data['line_number'],
                original_text=md_data['original_text']
            )
            session.add(macro_def)

        # Insert library extensions
        for le_data in parsed_data.get('library_extensions', []):
            lib_ext = LibraryExtension(
                filelist_id=filelist_id_map.get(le_data['filelist_id'], le_data['filelist_id']),
                extension=le_data['extension'],
                line_number=le_data['line_number'],
                position=le_data.get('position', 0)
            )
            session.add(lib_ext)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _format_flattened(result) -> str:
    """Format ParsedFilelist as a flattened Verilog-XL filelist.

    Preserves original line order and structure, expanding -f/-F inline
    with `// resolved start / end` markers. Comments are passed through.

    Args:
        result: ParsedFilelist instance with _parsed_data

    Returns:
        Flattened filelist string ready for use with simulators
    """
    filelists = result._parsed_data.get('filelists', [])
    if not filelists:
        return ""

    filelist_by_path = {fl['filepath']: fl for fl in filelists}

    def format_filelist(fl_data: dict, indent: str = "") -> list:
        """Recursively format a filelist and its nested includes."""
        lines = []

        for item in fl_data.get('line_items', []):
            item_type = item['item_type']
            resolved_text = item['resolved_text'] or item['original_text']

            if item_type == 'include_f':
                include_path = item['include_path']
                original_text = item['original_text']
                option_prefix = "-F" if original_text.startswith("-F") else "-f"

                lines.append(f"{indent}// resolved start: {option_prefix} {include_path}")
                nested_fl = filelist_by_path.get(include_path)
                if nested_fl:
                    lines.extend(format_filelist(nested_fl, indent))
                lines.append(f"{indent}// resolved end  : {option_prefix} {include_path}")

            else:
                # comment, file, lib_*, incdir, define, libext: pass through
                lines.append(f"{indent}{resolved_text}")

        return lines

    root_filelist = filelists[0]
    return "\n".join(format_filelist(root_filelist))


if __name__ == '__main__':
    cli()
