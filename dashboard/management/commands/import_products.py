import csv
from decimal import Decimal, InvalidOperation
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from dashboard.models import Product


def norm_ref(x):
    if x is None:
        return None
    s = str(x).strip()
    if s == "":
        return None
    # "8386810.0" -> "8386810"
    try:
        return str(int(float(s)))
    except Exception:
        return s


def to_decimal(x, default="0"):
    s = (str(x) if x is not None else default).strip().replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal(default)


class Command(BaseCommand):
    help = "Importe un CSV Décathlon dans la table Product (purge complète avant import)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Chemin du CSV")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = opts["csv_path"]

        # Purge complète
        before = Product.objects.count()
        Product.objects.all().delete()
        self.stdout.write(self.style.WARNING(f"Produits supprimés: {before}"))

        created, updated, skipped = 0, 0, 0

        try:
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, start=1):
                    pid = norm_ref(row.get("Reference Number"))
                    if not pid:
                        skipped += 1
                        self.stdout.write(
                            self.style.NOTICE(f"[Ligne {i}] ignorée: Reference Number manquant")
                        )
                        continue

                    name = (row.get("Title") or "").strip()
                    price = to_decimal(row.get("Price"), "0")
                    defaults = {
                        "name": name,
                        "description": (row.get("Features") or "").strip(),
                        "category": (row.get("Sub Category") or "").strip(),
                        "sport": (row.get("Sport") or "").strip(),
                        "brand": (row.get("Brand") or "").strip(),
                        "price": price,
                        "available": True,
                        "image_url": (row.get("Images 1") or "").strip(),
                        "image_url_alt": (row.get("Images 4") or "").strip(),
                    }

                    obj, is_created = Product.objects.update_or_create(
                        product_id=pid,
                        defaults=defaults,
                    )
                    if is_created:
                        created += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"[Créé] {pid} — {name}")
                        )
                    else:
                        updated += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"[Mis à jour] {pid} — {name}")
                        )

        except FileNotFoundError:
            raise CommandError(f"Fichier introuvable: {path}")

        self.stdout.write(self.style.SUCCESS(
            f"Import terminé. créés={created}, mis à jour={updated}, ignorés={skipped}"
        ))
