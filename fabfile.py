from fabric import api as fab
from fabric.colors import red as color_red, green

import fabtools
from fabtools import require
from fabtools.python import virtualenv


HOME_DIR = '/home/ubuntu'
DEMO_ENV = '{}/.virtualenvs/fabdemo'.format(HOME_DIR)
STATIC_DIR = '{}/static/'.format(HOME_DIR)
CODE_DIR = '{}/fabricdemo'.format(HOME_DIR)
GIT_URL = "https://github.com/jobdash/fabricdemo.git"
SERVER_TPL = """
# define an upstream server named gunicorn on localhost port 8000
upstream gunicorn {
    server localhost:8000;
}

server {
    listen %(port)d default;
    access_log /var/log/nginx/%(server_name)saccess.log;
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
        proxy_set_header Host            $host;
        proxy_set_header X-Real-IP       $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
"""

GUNICORN_TPL = """\
[program:gunicorn]
command = {virtualenv}/bin/gunicorn -w 4 fabricdemo.wsgi
directory = {directory}
user = ubuntu
autostart = true
autorestart = true
stdout_logfile = /var/log/supervisor/gunicorn.log
stderr_logfile = /var/log/supervisor/gunicorn_err.log
environment = {environment}
"""


@fab.task(alias='target')
def setup_hosts(target, user='ubuntu'):
    TARGET_HOSTS = {
        'demo': '107.170.250.36'
    }

    fab.env.hosts = TARGET_HOSTS.get(target)
    # fab.env.key_filename = SSH_KEY_FILE
    fab.env.user = user


@fab.task
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

    # Make sure that nginx is installed and running
    require.nginx.disabled('default')
    require.nginx.site(
        'fabdemo',
        template_contents=SERVER_TPL,
        port=80,
        server_alias='fabdemo',
        docroot=STATIC_DIR,
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
def install_reqs(changes=''):
    """
    Install production requriements.
    """
    if changes:
        print color_red("Found new python requirements: ")
        print color_red(changes)
    print green("New python requirements found, installing now")

    with fab.cd(CODE_DIR), virtualenv(DEMO_ENV):
        # make sure that any previously failed pip builds are removed.
        if fabtools.files.is_dir('/tmp/pip_build_ubuntu'):
            fabtools.files.remove('/tmp/pip_build_ubuntu', recursive=True)
        # install from the prod requirements
        require.python.requirements('requirements.txt')
