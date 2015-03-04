import digitalocean

from fabric import api as fab
from fabric.colors import red as color_red, green
from fabric.decorators import parallel
from fabric.utils import abort

import fabtools
from fabtools import require
from fabtools.python import virtualenv


DO_TOKEN = '1c6439c3b2431e46873a5c6a24e46cdddc9993a1f4915aa5d9485de01a3b3b55'
HOME_DIR = '/home/ubuntu'
DEMO_ENV = '{}/.virtualenvs/fabdemo'.format(HOME_DIR)
CODE_DIR = '{}/fabricdemo'.format(HOME_DIR)
STATIC_DIR = '{}/static'.format(CODE_DIR)
GIT_URL = "https://github.com/jobdash/fabricdemo.git"
SERVER_TPL = """
# define an upstream server named gunicorn on localhost port 8000
upstream gunicorn {
    server localhost:8000;
}

server {
    listen %(port)d default;
    access_log /var/log/nginx/%(server_name)s.access.log;
    error_log /var/log/nginx/%(server_name)s.error.log;
    try_files $uri @gunicorn;

    location @gunicorn {
        # repeated just in case
        client_max_body_size 0;

        # proxy to the gunicorn upstream defined above
        proxy_pass http://gunicorn;

        # makes sure the URLs don't actually say http://gunicorn
        proxy_redirect off;

        # If gunicorn takes > 5 minutes to respond, give up
        proxy_read_timeout 5m;

        # make sure these HTTP headers are set properly
        proxy_set_header Host            fabricdemo.com;
        proxy_set_header X-Real-IP       $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        autoindex on;
        alias %(static_dir)s;
    }
}
"""

GUNICORN_TPL = """\
[program:gunicorn]
command = {virtualenv}/bin/gunicorn -w 4 fabricdemo.wsgi
directory = {directory}
user = root
autostart = true
autorestart = true
stdout_logfile = /var/log/supervisor/gunicorn.log
stderr_logfile = /var/log/supervisor/gunicorn_err.log
environment = {environment}
"""


# Django helper
def manage(command):
    """
    Helper to simplify running Django manage commands.
    """
    cmd = 'python manage.py {} --settings=fabricdemo.settings.{}'.format(
        command, fab.env.django_settings)

    with fab.cd(CODE_DIR), virtualenv(DEMO_ENV):
        fab.run(cmd)


def get_droplets(name=None):
    manager = digitalocean.Manager(token=DO_TOKEN)
    droplets = manager.get_all_droplets()

    if name is None:
        return [d for d in droplets if 'fab' in d.name]

    return [d for d in droplets if 'fab' in d.name and name in d.name]


# Tasks
@fab.task
def list():
    """
    List out each server
    """

    for d in get_droplets():
        print "ID: {d.id}\t IP: {d.ip_address}\t Name: {d.name}".format(d=d)


@fab.task(alias='target')
def setup_hosts(target, user='ubuntu'):
    TARGET_HOST_SETTINGS = {
        'demo': 'dev',
        'web': 'prod'
    }

    if target not in TARGET_HOST_SETTINGS:
        abort(color_red(
            'Incorrect server group name.\n\nAvailable choices:\n{}'.format(
                '\n'.join(TARGET_HOST_SETTINGS.keys())
            )
        ))

    fab.env.django_settings = TARGET_HOST_SETTINGS.get(target)
    fab.env.hosts = [x.ip_address for x in get_droplets(target)]

    # fab.env.key_filename = SSH_KEY_FILE
    fab.env.user = user


@fab.task
@parallel
def setup():
    # make sure that th eubuntu user exists
    if not fabtools.files.is_dir(HOME_DIR):
        require.user('ubuntu')
        require.users.sudoer('ubuntu')

    # Make sure these packages are installed
    require.deb.uptodate_index()
    require.deb.packages([
        'build-essential',
        'git',
        'libncurses5-dev',
        'nginx',
        'npm',
        'python-dev',
        'python-pip',
        'supervisor',
    ])

    # Make sure that pip and virtualenv are installed
    # require.python.pip()
    require.python.packages([
        'virtualenv',
    ])
    # Make sure that the virtualenv exists
    require.python.virtualenv(DEMO_ENV)

    with fab.cd(HOME_DIR):
        require.git.working_copy(GIT_URL)

    with fab.cd(CODE_DIR), virtualenv(DEMO_ENV):
        require.python.requirements('requirements.txt')
        manage('collectstatic --noinput')

    # Make sure that nginx is installed and running
    require.nginx.disabled('default')
    require.nginx.site(
        'fabdemo',
        template_contents=SERVER_TPL,
        port=80,
        server_alias='fabdemo',
        static_dir=STATIC_DIR,
    )

    # require.nginx.server()
    ###
    # It seems that fabtools assumes that ubuntu is
    # running with systemd, but digital ocean is not
    # restart nginx manually.
    fab.sudo('service nginx restart')

    GUNICORN_ENV = ','.join([
        'DJANGO_SETTINGS_MODULE="fabricdemo.settings.prod"',
        'SECRET_KEY="_1kcf9pki$+ylug4ejl#x8yu_5zigk_0+7y7ainw!d-$y"'
    ])

    fab.sudo('service supervisor stop')
    # setup gunicorn
    CONF = GUNICORN_TPL.format(
        virtualenv=DEMO_ENV,
        directory=CODE_DIR,
        environment=GUNICORN_ENV
    )
    require.file(
        '/etc/supervisor/conf.d/gunicorn.conf',
        contents=CONF,
        use_sudo=True
    )
    fab.sudo('service supervisor start')
    fabtools.supervisor.update_config()

    if require.supervisor.process_status('gunicorn') == 'STOPPED':
        require.supervisor.start_process('gunicorn')
    # require.supervisor.process(
    #     'webapp',
    #     command='{env}/bin/gunicorn -w 4 fabricdemo.wsgi'.format(env=DEMO_ENV),
    #     directory=CODE_DIR,
    #     user='ubuntu',
    #     stdout_logfile='/var/log/supervisor/gunicorn.log',
    #     environment=GUNICORN_ENV
    # )


@fab.task
def deploy():
    with fab.cd(HOME_DIR):
        require.git.working_copy(GIT_URL)

    with fab.cd(CODE_DIR), virtualenv(DEMO_ENV):
        require.python.requirements('requirements.txt')
        manage('collectstatic --noinput')
    fabtools.supervisor.restart_process('gunicorn')
