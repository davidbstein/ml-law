#!/bin/bash
date >> ~/log.servicelog
/home/ubuntu/.local/bin/pipenv run python app.py >> ~/applog.servicelog
