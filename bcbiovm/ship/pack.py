"""Prepare a running process to execute remotely, moving files as necessary to shared infrastructure.
"""

def shared_filesystem(workdir, tmpdir=None):
    """Enable running processing within an optional temporary directory.

    workdir is assumed to be available on a shared filesystem, so we don't
    require any work to prepare.
    """
    return {"type": "shared", "workdir": workdir, "tmpdir": tmpdir}