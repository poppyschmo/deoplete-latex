
import os
import sys
from subprocess import check_output, CalledProcessError

"""Convenience functions for checking paths, statting files,
verifying commits, etc.
"""
# TODO - if adding more vcs stuff, migrate into a separate ``vcs.py`` module.


def sort_args(args):
    try:
        cwd, outfile = args
    except ValueError:
        fpath = os.path.relpath(args[0])
        cwd = os.path.commonpath((os.curdir, fpath))
        outfile = os.path.relpath(fpath, cwd)
        cwd = cwd if cwd else os.curdir
    fpath = os.path.join(cwd, outfile)
    return cwd, outfile, fpath


def is_path(*args, bail=False):
    cwd, outfile, fpath = sort_args(args)
    if os.path.exists(fpath):
        return True
    else:
        if bail is False:
            return False
        else:
            print('Path not found: "%s"...\nQuitting...' % fpath,
                  file=sys.stderr)
            raise SystemExit


def get_lines(*srcfiles, cwd=None):
    cwd = cwd if cwd else os.curdir
    for srcfile in srcfiles:
        fpath = os.path.join(cwd, srcfile)
        # XXX - unnecessary check, better to catch or let fail...
        is_path(fpath, bail=True)
        #
        with open(fpath) as f:
            yield f.readlines()


def save_backup(*args):
    cwd, outfile, fpath = sort_args(args)
    if not is_path(fpath):
        return
    #
    from datetime import datetime
    mt = datetime.fromtimestamp(os.path.getmtime(fpath))
    timestamp = datetime.strftime(mt, r'%Y%m%d_%H%M%S')
    tsuffix = '.' + timestamp + '.bak'
    suffixed = os.path.join(cwd, outfile.replace('.json', tsuffix))
    os.rename(fpath, suffixed)


def check_working_dir(path, hg=False, bail=False):
    """Assert working directory for git repo is clean."""
    # Check whether working directory is clean...
    if hg is False:
        cmd = 'git -C ' + path + ' status -s'
    else:
        cmd = 'hg --cwd ' + path + ' status'
    try:
        status = check_output(cmd.split())
    except CalledProcessError as cpe:
        print(cpe.returncode, cpe.output, file=sys.stderr)
        raise SystemExit
    else:
        status = status.decode(errors='replace').strip()
    #
    if bail is False:
        return True if status == '' else False
    elif status != '':
        print('Working directory not clean\nQuitting...', file=sys.stderr)
        raise SystemExit
    return True


def check_commit(path, chash, hg=False, bail=False):
    """Assert HEAD points to desired hash."""
    # Path exists?...
    is_path(path, bail=True)
    # Build command...
    if hg is False:
        cmd = 'git -C ' + path + ' --no-pager show @ --pretty=%H --no-patch'
    else:
        cmd = 'hg --cwd ' + path + ' parents --template {node}'
    #
    # XXX - These are shorter, but seems less legit...
    # ``git log -1 --pretty=%H`` and ``git merge-base @ @``.
    #
    try:
        last_hash = check_output(cmd.split())
    except CalledProcessError as cpe:
        print(cpe.returncode, cpe.output, file=sys.stderr)
        raise SystemExit
    else:
        last_hash = last_hash.decode(errors='replace').strip()
    #
    check_working_dir(path, hg=hg, bail=True)
    #
    if bail is False:
        return True if last_hash == chash else False
    elif last_hash != chash:
        print('HEAD doesn\'t point to %s\nQuitting...' % chash, file=sys.stderr)
        raise SystemExit
    return True
