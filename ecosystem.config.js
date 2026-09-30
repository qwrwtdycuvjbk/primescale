module.exports = {
  apps: [
    {
      name: "peopleremotely-next",
      cwd: "/var/www/peopleremotely",
      script: "node_modules/.bin/next",
      args: "start -p 3000",
      env: {
        NODE_ENV: "production",
        PORT: 3000,
      },
    },
    {
      name: "peopleremotely-django",
      cwd: "/var/www/peopleremotely/backend",
      script: "venv/bin/gunicorn",
      args: "config.wsgi:application --bind 127.0.0.1:8000 --workers 3",
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings",
      },
    },
    {
      name: "peopleremotely-celery",
      cwd: "/var/www/peopleremotely/backend",
      script: "venv/bin/celery",
      args: "-A config worker --loglevel=info",
      env: {
        DJANGO_SETTINGS_MODULE: "config.settings",
      },
    },
  ],
};
