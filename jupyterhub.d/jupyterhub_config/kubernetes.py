# Configuration file for JupyterHub
import os
import socket
import pwd


### VARIABLES ###
# Get configuration parameters from environment variables
DOCKER_NETWORK_NAME     = os.environ['DOCKER_NETWORK_NAME']
CVMFS_FOLDER            = os.environ['CVMFS_FOLDER']
EOS_USER_PATH           = os.environ['EOS_USER_PATH']
CONTAINER_IMAGE         = os.environ['CONTAINER_IMAGE']
LDAP_URI                = os.environ['LDAP_URI']
LDAP_PORT               = os.environ['LDAP_PORT']
LDAP_BASE_DN            = os.environ['LDAP_BASE_DN']
GALLERY_URL             = os.environ.get('GALLERY_URL')

c = get_config()

### Configuration for JupyterHub ###
# JupyterHub
c.JupyterHub.cookie_secret_file = '/srv/jupyterhub/cookie_secret'
c.JupyterHub.db_url = '/srv/jupyterhub/jupyterhub.sqlite'

# Logging
c.JupyterHub.log_level = 'DEBUG'
c.Spawner.debug = True
c.LocalProcessSpawner.debug = True

# Reach the Hub from local httpd (proxypass)
c.JupyterHub.ip = "127.0.0.1"
c.JupyterHub.port = 8000

c.JupyterHub.cleanup_servers = False
# Use local_home set to true to prevent calling the script that updates EOS tickets
c.JupyterHub.services = [
    {
        'name': 'cull-idle',
        'admin': True,
        'command': 'swanculler --cull_every=600 --timeout=14400 --disable_hooks=True --cull_users=True'.split(),
    },
    {
        'name': 'notifications',
        'command': 'swannotificationsservice --port 8989'.split(),
        'url': 'http://127.0.0.1:8989'
    }
]

# Reach the Hub from Jupyter containers
# NOTE: Containers are connected to a separate Docker network: DOCKER_NETWORK_NAME
#       The hub must listen on an IP address that is reachable from DOCKER_NETWORK_NAME
#       and not on "localhost"||"127.0.0.1" or any other name that could not be resolved
#       See also c.SwanSpawner.hub_ip_connect (https://github.com/jupyterhub/jupyterhub/issues/291)
try:
  hub_ip = socket.gethostbyname(socket.getfqdn())
except:
  print ("WARNING: Unable to identify iface IP from FQDN")
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.connect(("8.8.8.8", 80))
  hub_ip = s.getsockname()[0]
hub_port = 8080
c.JupyterHub.hub_ip = hub_ip
c.JupyterHub.hub_port = 8080

# Load the list of users with admin privileges and enable access
admins = set(open(os.path.join(os.path.dirname(__file__), 'adminslist'), 'r').read().splitlines())
c.Authenticator.admin_users = admins
c.JupyterHub.admin_access = True

### User Authentication ###
if ( os.environ['AUTH_TYPE'] == "shibboleth" ):
    print ("Authenticator: Using user-defined authenticator")
    c.JupyterHub.authenticator_class = '%%%SHIBBOLETH_AUTHENTICATOR_CLASS%%%'
    # %%% Additional SHIBBOLETH_AUTHENTICATOR_CLASS parameters here %%% #

elif ( os.environ['AUTH_TYPE'] == "local" ):
    print ("Authenticator: Using LDAP")
    c.JupyterHub.authenticator_class = 'ldapauthenticator.LDAPAuthenticator'
    c.LDAPAuthenticator.server_address = LDAP_URI
    c.LDAPAuthenticator.use_ssl = False
    c.LDAPAuthenticator.server_port = int(LDAP_PORT)
    if (LDAP_URI[0:8] == "ldaps://"):
      c.LDAPAuthenticator.use_ssl = True
    c.LDAPAuthenticator.bind_dn_template = 'uid={username},'+LDAP_BASE_DN

else:
    print ("ERROR: Authentication type not specified.")
    print ("Cannot start JupyterHub.")


### Configuration for single-user containers ###

# Spawn single-user's servers as Docker containers
c.JupyterHub.spawner_class = 'swanspawner.SwanDockerSpawner'
c.SwanSpawner.image = CONTAINER_IMAGE
c.SwanSpawner.remove_containers = True
c.SwanSpawner.options_form = open('/srv/jupyterhub/jupyterhub_form.html').read()
# JSON with default values (if not present, Spawner will crash...)
c.SwanSpawner.options_form_config = '/srv/jupyterhub/options_form_config.json'

# Instruct spawned containers to use the internal Docker network
c.SwanSpawner.use_internal_ip = True
c.SwanSpawner.network_name = DOCKER_NETWORK_NAME
c.SwanSpawner.extra_host_config = { 'network_mode': DOCKER_NETWORK_NAME }

# Single-user's servers extra config, CVMFS, EOS
#c.SwanSpawner.extra_host_config = { 'cap_drop': ['NET_BIND_SERVICE', 'SYS_CHROOT']}
c.SwanSpawner.read_only_volumes = { CVMFS_FOLDER : '/cvmfs' }

# Local home inside users' containers
#c.SwanSpawner.local_home = True		# If set to True, user <username> $HOME will be /scratch/<username>/
c.SwanSpawner.local_home = False
c.SwanSpawner.volumes = { EOS_USER_PATH : '/eos/user' }
c.SwanSpawner.check_cvmfs_status = False #For now it only checks if available in same place as Jupyterhub.

c.SwanSpawner.extra_env = dict(
    SHARE_CBOX_API_DOMAIN = "https://%%%CERNBOXGATEWAY_HOSTNAME%%%",
    SHARE_CBOX_API_BASE   = "/cernbox/swanapi/v1",
    HELP_ENDPOINT         = "https://raw.githubusercontent.com/swan-cern/help/up2u/",
    GALLERY_URL           = GALLERY_URL
)

# Now the Spawner expects the user uid to be injected by the authenticator
# Since ours don't do it, we set the UID as we were doing before: by resolving the user locally
def auth_state_hook(spawner, auth_state):
    spawner.user_uid = pwd.getpwnam(spawner.user.name).pw_uid
c.SwanSpawner.auth_state_hook = auth_state_hook

# local_home equal to true to hide the "always start with this config"
c.SpawnHandlersConfigs.local_home = True
c.SpawnHandlersConfigs.metrics_on = False #For now the metrics are hardcoded for CERN
c.SpawnHandlersConfigs.spawn_error_message = """SWAN could not start a session for your user, please try again. If the problem persists, please check:
<ul>
    <li>Do you have a CERNBox account? If not, click <a href="https://%%%CERNBOXGATEWAY_HOSTNAME%%%" target="_blank">here</a>.</li>
    <li>Check with the service manager that SWAN is running properly.</li>
</ul>"""
