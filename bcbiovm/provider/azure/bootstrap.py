"""
Helper class for updating or installing the bcbio and its requirements.
"""
from bcbiovm.common import constant
from bcbiovm.provider import base


class Bootstrap(base.Bootstrap):

    """
    Update or install the bcbio and its requirements.
    """

    def __init__(self, provider, config, cluster_name, reboot, verbose):
        """
        :param provider:       an instance of
                               :class bcbiovm.provider.base.BaseCloudProvider:
        :param config:         elasticluster config file
        :param cluster_name:   cluster name
        :param reboot:         whether to upgrade and restart the host OS
        :param verbose:        increase verbosity
        """
        super(Bootstrap, self).__init__(provider, config, cluster_name,
                                        reboot, verbose)

    def gof3r(self):
        """Install gof3r."""
        return self._run_playbook(constant.PLAYBOOK.GOF3R)