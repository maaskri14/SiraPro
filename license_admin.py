from __future__ import annotations

import argparse
from licensing import create_license


parser = argparse.ArgumentParser(description="Créer une licence CV Pro")
parser.add_argument("email")
parser.add_argument("--plan", choices=["monthly", "annual"], default="annual")
parser.add_argument("--days", type=int)
args = parser.parse_args()
key = create_license(args.email, args.plan, args.days)
print(f"Licence créée pour {args.email}: {key}")

