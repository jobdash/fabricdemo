from fabric import api as fab
from fabric.colors import red as color_red, green
from fabric.utils import abort

import fabtools
from fabtools import require
from fabtools.python import virtualenv


HOME_DIR = '/home/ubuntu'
DEMO_ENV = '{}/.virtualenvs/fabdemo'.format(HOME_DIR)
CODE_DIR = '{}/fabricdemo'.format(HOME_DIR)
STATIC_DIR = '{}/static'.format(CODE_DIR)
GIT_URL = "https://github.com/jobdash/fabricdemo.git"
NGINX_TPL = """
user www-data;
worker_processes 4;
pid /run/nginx.pid;

events {
    worker_connections 768;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    access_log /var/log/nginx/access.log;
    error_log /var/log/nginx/error.log;
    gzip on;
    gzip_disable "msie6";

    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_buffers 16 8k;
    gzip_http_version 1.1;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites-enabled/*;
}
"""
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
user = ubuntu
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


# Git helpers
def find_any_migrations(start_sha, end_sha):
    """
    Search through the GIT history to determine if there are any DB migrations.
    """
    find_changes = (
        "git diff-tree --no-commit-id --name-only -r {start}..{end}"
        " | grep 'migrations'"
    ).format(start=start_sha, end=end_sha)

    with fab.cd(CODE_DIR):
        print green("Looking for migrations")
        # make sure we run the command from the code root directory
        return fab.run(find_changes, warn_only=True, quiet=True)


def find_any_python_installs(start_sha, end_sha):
    """
    Check if any requirements files have changed
    """
    find_changes = (
        "git diff-tree --no-commit-id --name-only -r {start}..{end}"
        " | grep 'requirements'"
    ).format(start=start_sha, end=end_sha)

    with fab.cd(CODE_DIR):
        print green("Looking for new requirements")
        # make sure we run the command from the code root directory
        return fab.run(find_changes, warn_only=True, quiet=True)


def find_static_file_changes(start_sha, end_sha):
    """
    Check if any staticfiles have been changed/added/removed
    """
    find_changes = (
        "git diff-tree --no-commit-id --name-only -r {start}..{end}"
        " | grep 'staticfiles'"
    ).format(start=start_sha, end=end_sha)

    with fab.cd(CODE_DIR):
        print green("Looking for changes in staticfiles")
        # make sure we run the command from the code root directory
        return fab.run(find_changes, warn_only=True, quiet=True)


# Tasks
@fab.task(alias='target')
def setup_hosts(target, user='ubuntu'):
    TARGET_HOSTS = {
        'demo': ('107.170.250.36', 'dev'),
        'web': ('107.170.250.36', 'prod')
    }

    if target not in TARGET_HOSTS:
        abort(color_red(
            'Incorrect server group name.\n\nAvailable choices:\n{}'.format(
                '\n'.join(TARGET_HOSTS.keys())
            )
        ))

    fab.env.hosts, fab.env.django_settings = TARGET_HOSTS.get(target)
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

    with fab.cd(CODE_DIR):
        # install the javascript packaging tools
        fab.run('npm install')
        fab.run('bower install')

    with fab.cd(CODE_DIR), virtualenv(DEMO_ENV):
        require.python.requirements('requirements.txt')
        # build the
        fab.run('gulp')
        manage('collectstatic --noinput')

    # Make sure that nginx is installed and running
    # We make sure that NGINX has gzip enabled.
    require.file('/etc/nginx/nginx.conf', contents=NGINX_TPL, user_sudo=True)
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
