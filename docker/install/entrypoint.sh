#! /bin/bash

set -e

source ~/.profile

# exec "$@"
exec ""poetry run ipython -i -- load-db-and-tables.py --sqlite-path vlr-gg.db --table-names matches""
