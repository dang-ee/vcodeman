"""Click-based CLI for vcodeman."""

import sys
from pathlib import Path

import click

from vcodeman._version import __version__


CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__)
@click.option('-v', '--verbose', count=True, help='Verbosity (-v/-vv/-vvv)')
@click.option('-q', '--quiet', is_flag=True, help='Suppress non-error output')
@click.pass_context
def cli(ctx, verbose, quiet):
    """Verilog-XL filelist parser and flattener.

    Example: vcodeman parse design.f -o flat.f
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet


@cli.command()
@click.argument('filelist', type=click.Path(exists=True, readable=True, path_type=Path))
@click.option('-o', '--output', type=click.Path(path_type=Path), help='Output file (default: stdout)')
@click.option(
    '-f', '--format',
    type=click.Choice(['text', 'json', 'sqlite'], case_sensitive=False),
    default='text',
    help='Output format (default: text)'
)
@click.option('--strict-env', is_flag=True, help='Fail on undefined env vars')
@click.option('--env', 'env_pairs', multiple=True, metavar='KEY=VALUE', help='Inject env var (repeatable)')
@click.option('--skip-ext', 'skip_exts', multiple=True, metavar='EXT', help='Comment out by extension, text only (repeatable)')
@click.option('--incdir-first', is_flag=True, help='Move all +incdir+ entries to the top, text only')
@click.option('--no-comments', is_flag=True, help='Strip all comments from output, text only')
@click.pass_context
def parse(ctx, filelist, output, format, strict_env, env_pairs, skip_exts, incdir_first, no_comments):
    """Flatten a filelist, expanding all nested -f/-F includes.

    Example: vcodeman parse design.f -o flat.f
    """
    import json
    import os
    from vcodeman.parser import FilelistParser
    from vcodeman.resolver import CircularReferenceError, UndefinedVariableError

    verbose = ctx.obj.get('verbose', 0)
    quiet = ctx.obj.get('quiet', False)

    if not quiet and verbose > 0:
        click.echo(f"Parsing: {filelist}", err=True)

    for pair in env_pairs:
        if '=' not in pair:
            click.secho(f"Error: --env must be KEY=VALUE (got: {pair!r})", fg='red', err=True)
            sys.exit(2)
        key, _, value = pair.partition('=')
        if not key:
            click.secho(f"Error: --env key may not be empty (got: {pair!r})", fg='red', err=True)
            sys.exit(2)
        os.environ[key] = value

    try:
        parser = FilelistParser(strict_env_vars=strict_env)
        result = parser.parse(filelist_path=filelist)

        if format == 'json':
            output_data = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
            if output:
                output.write_text(output_data)
                if not quiet:
                    click.echo(f"Output written to: {output}", err=True)
            else:
                click.echo(output_data)
        elif format == 'sqlite':
            if not output:
                output = Path(filelist).with_suffix('.db')
            _export_sqlite(result, output)
            if not quiet:
                click.echo(f"SQLite database written to: {output}", err=True)
        else:
            normalized_skip_exts = {
                e if e.startswith('.') else f'.{e}'
                for e in skip_exts
            }
            output_data = _format_flattened(
                result,
                skip_exts=normalized_skip_exts,
                incdir_first=incdir_first,
                no_comments=no_comments,
            )
            if output:
                output.write_text(output_data)
                if not quiet:
                    click.echo(f"Output written to: {output}", err=True)
            else:
                click.echo(output_data)

        if not quiet and verbose > 0:
            click.echo("Parse completed successfully", err=True)

    except CircularReferenceError as e:
        click.secho("Error: Circular reference detected", fg='red', err=True)
        click.echo(f"  {e}", err=True)
        sys.exit(1)
    except UndefinedVariableError as e:
        click.secho("Error: Undefined environment variable", fg='red', err=True)
        click.echo(f"  {e}", err=True)
        sys.exit(1)
    except FileNotFoundError as e:
        click.secho("Error: File not found", fg='red', err=True)
        click.echo(f"  {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.secho("Error: Parse failed", fg='red', err=True)
        click.echo(f"  {e}", err=True)
        if verbose > 1:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def _export_sqlite(result, output_path: Path) -> None:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from vcodeman.models import (
        Base, Filelist, FileEntry, LibraryDirectory, LibraryFile,
        IncludeDirectory, MacroDefinition, LibraryExtension, LineItem, ParsedFilelist
    )

    if output_path.exists():
        output_path.unlink()

    file_engine = create_engine(f"sqlite:///{output_path}")
    Base.metadata.create_all(file_engine)
    SessionLocal = sessionmaker(bind=file_engine)
    session = SessionLocal()

    try:
        parsed_data = result._parsed_data
        if not parsed_data:
            return

        parsed_filelist = ParsedFilelist(
            root_filepath=result.root_filepath,
            timestamp=result.timestamp,
            warnings=result.warnings,
            errors=result.errors
        )
        session.add(parsed_filelist)
        session.flush()

        filelist_id_map = {}

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

        for ld_data in parsed_data.get('library_directories', []):
            lib_dir = LibraryDirectory(
                filelist_id=filelist_id_map.get(ld_data['filelist_id'], ld_data['filelist_id']),
                dirpath=ld_data['dirpath'],
                original_path=ld_data['original_path'],
                line_number=ld_data['line_number'],
                exists=ld_data.get('exists', True)
            )
            session.add(lib_dir)

        for lf_data in parsed_data.get('library_files', []):
            lib_file = LibraryFile(
                filelist_id=filelist_id_map.get(lf_data['filelist_id'], lf_data['filelist_id']),
                filepath=lf_data['filepath'],
                original_path=lf_data['original_path'],
                line_number=lf_data['line_number'],
                exists=lf_data.get('exists', True)
            )
            session.add(lib_file)

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

        for md_data in parsed_data.get('macro_definitions', []):
            macro_def = MacroDefinition(
                filelist_id=filelist_id_map.get(md_data['filelist_id'], md_data['filelist_id']),
                name=md_data['name'],
                value=md_data.get('value'),
                line_number=md_data['line_number'],
                original_text=md_data['original_text']
            )
            session.add(macro_def)

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


def _format_flattened(
    result,
    skip_exts: set[str] | None = None,
    incdir_first: bool = False,
    no_comments: bool = False,
) -> str:
    filelists = result._parsed_data.get('filelists', [])
    if not filelists:
        return ""

    skip_exts = skip_exts or set()
    filelist_by_path = {fl['filepath']: fl for fl in filelists}

    def collect_incdirs(fl_data: dict) -> list[str]:
        """Recursively collect all +incdir+ lines across nested includes."""
        incdirs = []
        for item in fl_data.get('line_items', []):
            if item['item_type'] == 'incdir':
                incdirs.append(item['resolved_text'] or item['original_text'])
            elif item['item_type'] == 'include_f':
                nested_fl = filelist_by_path.get(item['include_path'])
                if nested_fl:
                    incdirs.extend(collect_incdirs(nested_fl))
        return incdirs

    def format_filelist(fl_data: dict, indent: str = "", skip_incdirs: bool = False) -> list[str]:
        lines = []
        for item in fl_data.get('line_items', []):
            item_type = item['item_type']
            resolved_text = item['resolved_text'] or item['original_text']

            if item_type == 'include_f':
                include_path = item['include_path']
                original_text = item['original_text']
                option_prefix = "-F" if original_text.startswith("-F") else "-f"
                if not no_comments:
                    lines.append(f"{indent}// resolved start: {option_prefix} {include_path}")
                nested_fl = filelist_by_path.get(include_path)
                if nested_fl:
                    lines.extend(format_filelist(nested_fl, indent, skip_incdirs))
                if not no_comments:
                    lines.append(f"{indent}// resolved end  : {option_prefix} {include_path}")
            elif item_type == 'incdir' and skip_incdirs:
                pass  # already hoisted to top
            elif item_type == 'comment' and no_comments:
                pass
            elif item_type == 'file' and skip_exts:
                ext = Path(resolved_text).suffix
                if ext in skip_exts:
                    if not no_comments:
                        lines.append(f"{indent}// skipped ({ext}): {resolved_text}")
                else:
                    lines.append(f"{indent}{resolved_text}")
            else:
                lines.append(f"{indent}{resolved_text}")

        return lines

    root_filelist = filelists[0]

    if incdir_first:
        incdirs = collect_incdirs(root_filelist)
        rest = format_filelist(root_filelist, skip_incdirs=True)
        return "\n".join(incdirs + rest)

    return "\n".join(format_filelist(root_filelist))


if __name__ == '__main__':
    cli()
