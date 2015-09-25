"""Run a bcbio-nextgen analysis inside of an isolated docker container.
"""
from __future__ import print_function

import os
import pwd
import uuid
import sys

import yaml

from bcbio import log
from bcbiovm.client import tools as client_tools
from bcbiovm.docker import manage as docker_manage
from bcbiovm.docker import mounts as docker_mounts
from bcbiovm.docker import remap as docker_remap
from bcbiovm.provider import factory


def do_analysis(args, dockerconf, mounts):
    """Run a full analysis on a local machine, utilizing multiple cores.
    """
    work_dir = os.getcwd()
    with open(args.sample_config) as in_handle:
        sample_config, dmounts = docker_mounts.update_config(
            yaml.load(in_handle), args.fcdir)
    mounts.extend(dmounts)
    mounts.append("%s:%s" % (work_dir, dockerconf["work_dir"]))
    system_config, system_mounts = _read_system_config(dockerconf,
                                                       args.systemconfig,
                                                       args.datadir)
    system_cfile = os.path.join(work_dir, "bcbio_system-forvm.yaml")
    with open(system_cfile, "w") as out_handle:
        yaml.dump(system_config, out_handle, default_flow_style=False,
                  allow_unicode=False)

    sample_cfile = os.path.join(work_dir, "bcbio_sample-forvm.yaml")
    with open(sample_cfile, "w") as out_handle:
        yaml.dump(sample_config, out_handle, default_flow_style=False,
                  allow_unicode=False)

    in_files = [os.path.join(dockerconf["work_dir"], os.path.basename(path))
                for path in (system_cfile, sample_cfile)]

    log.setup_local_logging({"include_time": False})
    docker_manage.run_bcbio_cmd(
        args.image, mounts + system_mounts,
        in_files + ["--numcores", str(args.numcores),
                    "--workdir=%s" % dockerconf["work_dir"]])


def do_runfn(fn_name, fn_args, cmd_args, parallel, dockerconf, ports=None):
    """"Run a single defined function inside a docker container, returning results.
    """
    reconstitute = factory.get_ship(cmd_args["pack"].type).reconstitute()
    prepare_system = client_tools.Common.prepare_system
    mounts = []

    if cmd_args.get("sample_config"):
        with open(cmd_args["sample_config"]) as in_handle:
            _, mounts = docker_mounts.update_config(yaml.load(in_handle),
                                                    cmd_args["fcdir"])

    datadir, fn_args = reconstitute.prepare_datadir(cmd_args["pack"], fn_args)
    if "orig_systemconfig" in cmd_args:
        orig_sconfig = _get_system_configfile(cmd_args["orig_systemconfig"],
                                              datadir)
        orig_galaxydir = os.path.dirname(orig_sconfig)
        mounts.append("%s:%s" % (orig_galaxydir, orig_galaxydir))

    work_dir, fn_args, finalizer = reconstitute.prepare_workdir(
        cmd_args["pack"], parallel, fn_args)

    mounts.extend(prepare_system(datadir, dockerconf["biodata_dir"]))
    mounts.append("%s:%s" % (work_dir, dockerconf["work_dir"]))
    mounts.append("{home}:{home}"
                  .format(home=pwd.getpwuid(os.getuid()).pw_dir))

    reconstitute.prep_systemconfig(datadir, fn_args)
    _, system_mounts = _read_system_config(dockerconf,
                                           cmd_args["systemconfig"],
                                           datadir)

    all_mounts = mounts + system_mounts

    argfile = os.path.join(work_dir, "runfn-%s-%s.yaml" %
                           (fn_name, uuid.uuid4()))
    with open(argfile, "w") as out_handle:
        yaml.safe_dump(docker_remap.external_to_docker(fn_args, all_mounts),
                       out_handle, default_flow_style=False,
                       allow_unicode=False)
    docker_argfile = os.path.join(dockerconf["work_dir"],
                                  os.path.basename(argfile))
    outfile = "%s-out%s" % os.path.splitext(argfile)
    out = None
    docker_manage.run_bcbio_cmd(cmd_args["image"], all_mounts,
                                ["runfn", fn_name, docker_argfile],
                                ports=ports)
    if os.path.exists(outfile):
        with open(outfile) as in_handle:
            out = docker_remap.docker_to_external(yaml.safe_load(in_handle),
                                                  all_mounts)
    else:
        print("Subprocess in docker container failed")
        sys.exit(1)
    out = finalizer(out)
    for f in [argfile, outfile]:
        if os.path.exists(f):
            os.remove(f)
    return out


def local_system_config(systemconfig, datadir, work_dir):
    """Create a ready to run local system configuration file.
    """
    config = _get_system_config(systemconfig, datadir)
    system_cfile = os.path.join(work_dir, "bcbio_system-prep.yaml")
    with open(system_cfile, "w") as out_handle:
        yaml.dump(config, out_handle, default_flow_style=False,
                  allow_unicode=False)
    return system_cfile


def _get_system_configfile(systemconfig, datadir):
    """Retrieve system configuration file from input or default directory.
    """
    if systemconfig:
        if not os.path.isabs(systemconfig):
            return os.path.normpath(os.path.join(os.getcwd(), systemconfig))
        else:
            return systemconfig
    else:
        return os.path.join(datadir, "galaxy", "bcbio_system.yaml")


def _get_system_config(systemconfig, datadir):
    """Retrieve a system configuration with galaxy references specified.
    """
    f = _get_system_configfile(systemconfig, datadir)
    with open(f) as in_handle:
        config = yaml.load(in_handle)
    if "galaxy_config" not in config:
        config["galaxy_config"] = os.path.join(os.path.dirname(f),
                                               "universe_wsgi.ini")
    return config


def _read_system_config(dockerconf, systemconfig, datadir):
    # FIXME(alexandrucoman): Unused argument 'dockerconf'
    # pylint: disable=unused-argument
    config = _get_system_config(systemconfig, datadir)
    # Map external galaxy specifications over to docker container
    dmounts = []
    for k in ["galaxy_config"]:
        if k in config:
            dirname, base = os.path.split(os.path.normpath(
                os.path.realpath(config[k])))
            dmounts.append("%s:%s" % (dirname, dirname))
            dmounts.extend(docker_mounts.find_genome_directory(dirname))
            config[k] = str(os.path.join(dirname, base))
    return config, dmounts
