#!/usr/bin/env bash
#
# Prépare une base de démonstration complète pour l'application PDA.
#
# Usage :
#   ./scripts/demo-start.sh                 # base « pda_demo »
#   DEMO_DB=essai ./scripts/demo-start.sh   # autre nom de base
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [[ ! -f .env ]]; then
    echo "Fichier .env absent : copiez .env.example vers .env" >&2
    echo "puis renseignez les mots de passe PostgreSQL." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

DEMO_DB="${DEMO_DB:-pda_demo}"
ODOO_PORT="${ODOO_PORT:-8069}"

echo "==> Démarrage de PostgreSQL"
docker compose up -d db

echo "==> Installation de pda_base et pda_demo dans la base « ${DEMO_DB} »"
echo "    (peut prendre quelques minutes au premier lancement)"
docker compose run --rm odoo odoo \
    -d "${DEMO_DB}" \
    -i pda_base,pda_demo \
    --without-demo \
    --load-language=fr_FR \
    --stop-after-init

echo "==> Démarrage d'Odoo"
docker compose up -d odoo

cat <<EOF

Démonstration prête : http://localhost:${ODOO_PORT}

Comptes :
  Opérateur PDA      pda.operateur    / pda.operateur
  Responsable PDA    pda.responsable  / pda.responsable
  Administrateur     admin            / admin

Écran PDA : menu « PDA > Scanner »
Guide de démonstration : docs/DEMO_CLIENT.md
EOF
