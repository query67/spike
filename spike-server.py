#! /usr/bin/env python
#
# spike-server.py
# 
# this: v0.8.22 - 2014-10-10
#
import base64
import os
import logging
import argparse
from os.path import dirname, abspath, isdir
from shutil import move
from time import time, strftime, localtime

from spike import create_app, seeds, version, model
from spike.model import db, Settings, NaxsiRuleSets
from spike.model.naxsi_rules import ValueTemplates


def run():
    app = create_app(config_file())

    try:
        app_port = int(app.config["APP_PORT"])
    except:
        app_port = 5555
    try:
        app_host = app.config["APP_HOST"]
    except:
        app_host = "127.0.0.1"

    db.init_app(app)
    app.test_request_context().push()

    try:
        backup_dir = Settings.query.filter(Settings.name == 'backup_dir').first()
        app.config["BACKUP_DIR"] = backup_dir.value
    except:
        app.config["BACKUP_DIR"] = "backups"

    try:
        eo_offset = Settings.query.filter(Settings.name == 'rules_offset').first()
        app.config["NAXSI_RULES_OFFSET"] = eo_offset.value
    except:
        app.config["NAXSI_RULES_OFFSET"] = 20000

    try:
        app.config["RULESET_HEADER"] = app.config["RULESET_HEADER"]
    except:
        app.config["RULESET_HEADER"] = ''

    logging.info("Spike is running on %s:%s", app_host, app_port)
    app.run(debug=True, host=app_host, port=app_port)


def spike_init():
    """ Import some data into Spkie internal DB, in order to be able to run it """
    it = ts = int(time())
    logging.info("Initializing Spike")

    ds = strftime("%F - %H:%M", localtime(time()))
    app = create_app(config_file())

    bd = seeds.settings_seeds['backup_dir']
    if not isdir(bd):
        logging.info("rulesets_backup_dir not found, creating: %s", bd)
        os.mkdir(bd)

    db_files = app.config["SQLALCHEMY_BINDS"]

    for sqldb in db_files:
        p1 = os.path.join('spike', db_files[sqldb].replace("sqlite:///", ""))
        if os.path.isfile(p1):
            logging.info("Existing db found (%s) creating backup", sqldb)
            move(p1, os.path.join(p1, it))
            logging.info("copy: %s.%s", p1, it)

    app.test_request_context().push()
    db.init_app(app)

    with app.app_context():
        db.create_all()

    logging.info("filling default_vals")

    for v in seeds.vtemplate_seeds:
        logging.info("adding templates: %s" , v)
        for val in seeds.vtemplate_seeds[v]:
            db.session.add(ValueTemplates(v, val))

    for r in seeds.rulesets_seeds:
        logging.info("adding ruleset: %s / %s", r, seeds.rulesets_seeds[r])
        rmks = "naxsi-ruleset for %s / auto-created %s" % (r, ds)
        db.session.add(NaxsiRuleSets(seeds.rulesets_seeds[r], r, rmks, ts, ts))

    for s in seeds.settings_seeds:
        logging.info("adding setting: %s", s)
        db.session.add(Settings(s, seeds.settings_seeds[s]))
    db.session.commit()

    with open(config_file(), "a") as f:
        f.write('\nSECRET_KEY="%s"' % base64.b64encode(os.urandom(128)))

    logging.info('Spike initialization completed')


def spike_update():
    logging.info('Updating spike')
    os.system("git pull 2>&1")
    app = create_app(config_file())

    from spike.model import db
    from spike.model import Settings

    app.test_request_context().push()
    db.init_app(app)

    for s in seeds.settings_seeds:
        if not model.check_constraint("settings", s):
            logging.info("adding setting: %s", s)
            db.session.add(Settings(s, seeds.settings_seeds[s]))
        else:
            logging.info("Known setting: %s", s)
    db.session.commit()

    logging.info('Spike is now up to date')


def config_file():
    return os.path.join(dirname(abspath(__name__)), 'config.cfg')


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(message)s')
    parser = argparse.ArgumentParser(description='Spike %s' % version)
    parser.add_argument('command', help='Run the spike server', choices=['run', 'init', 'update'])
    args = parser.parse_args()

    if args.command == 'run':
        run()
    elif args.command == 'init':
        spike_init()
    elif args.command == 'update':
        spike_update()
