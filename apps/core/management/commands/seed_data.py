import random
from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from PIL import Image, ImageDraw, ImageFont

from apps.bookings.models import Booking, BookingSeat
from apps.shows.models import Category, Performance, PerformancePrice, Show
from apps.theaters.models import (
    Auditorium,
    AuditoriumZone,
    Seat,
    Theater,
    TheaterAdmin,
)


# Desaturated palette reused for the generated placeholder images.
PLACEHOLDER_COLORS = [
    (86, 104, 132),
    (110, 130, 122),
    (140, 118, 120),
    (120, 116, 140),
    (132, 124, 104),
    (104, 128, 140),
]


def make_placeholder(text, index=0, size=(800, 600)):
    """Render a simple, offline placeholder image and return it as a ContentFile."""
    bg = PLACEHOLDER_COLORS[index % len(PLACEHOLDER_COLORS)]
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.load_default(size=48)
    except TypeError:  # Pillow < 10 has no size argument
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size[0] - tw) / 2, (size[1] - th) / 2),
        text,
        fill=(245, 245, 245),
        font=font,
    )

    buffer = BytesIO()
    img.save(buffer, format="JPEG", quality=82)
    return ContentFile(buffer.getvalue())


class Command(BaseCommand):
    help = "Seed iniziale per ambiente di sviluppo (azzera e rigenera i dati di dominio)."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write("Avvio seed dati (azzeramento e rigenerazione)...")

        # ── Flush existing domain data (order-safe for FK / PROTECT) ──────────
        BookingSeat.objects.all().delete()
        Booking.objects.all().delete()
        PerformancePrice.objects.all().delete()
        Performance.objects.all().delete()
        Seat.objects.all().delete()
        AuditoriumZone.objects.all().delete()
        Auditorium.objects.all().delete()
        Show.objects.all().delete()
        Theater.objects.all().delete()

        # ── Roles ─────────────────────────────────────────────────────────────
        role_names = ["artist", "manager", "client"]
        for role_name in role_names:
            Group.objects.get_or_create(name=role_name)

        # ── Categories ────────────────────────────────────────────────────────
        categories = ["Classico", "Commedia", "Drammatico", "Musical", "Moderno"]
        category_map = {}
        for name in categories:
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name)},
            )
            category_map[name] = category

        # ── Users ─────────────────────────────────────────────────────────────
        User = get_user_model()

        def create_user(username, email, password, group, is_superuser=False, is_staff=False):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if created:
                user.set_password(password)
            user.is_superuser = is_superuser
            user.is_staff = is_staff or is_superuser
            user.save()
            if group:
                user.groups.add(Group.objects.get(name=group))
            return user

        admin_user = create_user("admin", "admin@example.com", "Admin123!", None, is_superuser=True, is_staff=True)
        artist_user = create_user("artista", "artista@example.com", "Artist123!", "artist")
        artist_user_2 = create_user("artista2", "artista2@example.com", "Artist123!", "artist")
        manager_user = create_user("gestore", "gestore@example.com", "Gestore123!", "manager")
        # A second manager left intentionally without any theater assignment,
        # to exercise the "Nessun teatro" empty state.
        manager_unassigned = create_user("gestore2", "gestore2@example.com", "Gestore123!", "manager")
        customer_user = create_user("cliente", "cliente@example.com", "Cliente123!", "client")

        client_specs = [
            ("cliente2", "cliente2@example.com"),
            ("cliente3", "cliente3@example.com"),
            ("cliente4", "cliente4@example.com"),
            ("cliente5", "cliente5@example.com"),
            ("cliente6", "cliente6@example.com"),
        ]
        extra_customers = [
            create_user(username, email, "Cliente123!", "client")
            for username, email in client_specs
        ]

        artists = [artist_user, artist_user_2]

        # ── Theaters (5) ──────────────────────────────────────────────────────
        theater_specs = [
            ("Teatro Centrale", "Teatro storico nel centro cittadino.", "Via Roma 10", "Milano", "MI", "20121", 45.4685, 9.1824),
            ("Teatro Aurora", "Spazio moderno per eventi e musical.", "Corso Torino 45", "Torino", "TO", "10121", 45.0703, 7.6869),
            ("Teatro Verdi", "Elegante sala ottocentesca affacciata sull'Arno.", "Via Ghibellina 99", "Firenze", "FI", "50122", 43.7696, 11.2558),
            ("Teatro Massimo", "Grande teatro lirico nel cuore della città.", "Piazza Verdi 1", "Palermo", "PA", "90138", 38.1206, 13.3565),
            ("Teatro La Fenice", "Prestigioso teatro affacciato sui canali.", "Campo San Fantin 1965", "Venezia", "VE", "30124", 45.4337, 12.3339),
        ]

        theaters = []
        for i, (name, desc, addr, city, prov, cap, lat, lng) in enumerate(theater_specs):
            theater = Theater.objects.create(
                name=name,
                description=desc,
                address=addr,
                city=city,
                province=prov,
                postal_code=cap,
                phone="0" + str(1000000 + i),
                email=f"info@{slugify(name)}.example.com",
                opening_hours="Mar-Dom 10:00-19:00",
                latitude=lat,
                longitude=lng,
            )
            theater.photo.save(f"{slugify(name)}.jpg", make_placeholder(name, i), save=True)
            theaters.append(theater)

        # ── Auditoriums + zones + seats ───────────────────────────────────────
        zone_defs = [
            ("Platea", 5, 12, 1),
            ("Galleria", 3, 10, 2),
            ("Loggione", 2, 8, 3),
        ]

        auditoriums = []
        for i, theater in enumerate(theaters):
            # Every theater has a main hall; the first two also get a second, smaller hall.
            hall_names = ["Sala Grande"]
            if i < 2:
                hall_names.append("Sala Piccola")
            for hall_name in hall_names:
                auditorium = Auditorium.objects.create(theater=theater, name=hall_name)
                for zone_name, rows, spr, order in zone_defs:
                    AuditoriumZone.objects.create(
                        auditorium=auditorium,
                        zone=zone_name,
                        rows=rows,
                        seats_per_row=spr,
                        order=order,
                    )
                auditorium.regenerate_seats()
                auditoriums.append(auditorium)

        # ── Manager assignments ───────────────────────────────────────────────
        for theater in theaters[:3]:
            TheaterAdmin.objects.get_or_create(theater=theater, user=manager_user)

        # ── Shows (6) with poster + cover ─────────────────────────────────────
        show_specs = [
            ("La commedia degli errori", "Una commedia brillante tra scambi di identità e ritmo serrato.", "Commedia", 110),
            ("Note di Mezzanotte", "Musical contemporaneo con orchestra dal vivo.", "Musical", 130),
            ("Amleto", "Il grande classico shakespeariano in una nuova regia.", "Drammatico", 160),
            ("Il flauto magico", "Opera senza tempo tra magia e simbolismo.", "Classico", 145),
            ("Cabaret Moderno", "Spettacolo di varietà con sguardo contemporaneo.", "Moderno", 95),
            ("Sogno di una notte", "Fiaba corale ricca di equivoci e incanti.", "Commedia", 120),
        ]

        shows = []
        for i, (title, desc, cat, duration) in enumerate(show_specs):
            show = Show.objects.create(
                artist=artists[i % len(artists)],
                title=title,
                description=desc,
                category=category_map[cat],
                duration_minutes=duration,
            )
            show.poster.save(f"{slugify(title)}-poster.jpg", make_placeholder(title, i), save=True)
            show.cover.save(f"{slugify(title)}-cover.jpg", make_placeholder(title, i + 3, size=(1200, 400)), save=True)
            shows.append(show)

        # ── Performances (24) spread across theaters and dates ────────────────
        performances = []
        base = timezone.localtime(timezone.now()).replace(minute=0, second=0, microsecond=0)
        hours = [18, 20, 21]
        for i in range(24):
            show = shows[i % len(shows)]
            auditorium = auditoriums[i % len(auditoriums)]
            starts_at = (base + timedelta(days=3 + i)).replace(hour=hours[i % len(hours)], minute=30)
            performance = Performance.objects.create(
                show=show,
                auditorium=auditorium,
                starts_at=starts_at,
                status=Performance.STATUS_SCHEDULED,
                confirmed_by_artist=True,
                confirmed_by_artist_at=timezone.now(),
                created_by=manager_user,
            )
            performances.append(performance)

            zones = list(auditorium.zones.order_by("order", "id"))
            for index, zone in enumerate(zones, start=1):
                PerformancePrice.objects.create(
                    performance=performance,
                    auditorium_zone=zone,
                    price=18 + index * 6,
                )

        # ── Bookings ───────────────────────────────────────────────────────────
        # reserved_by_performance tracks which seats are already taken per
        # performance, across every customer, to respect BookingSeat's
        # unique_together("performance", "seat") constraint.
        reserved_by_performance: dict[int, set[int]] = {p.id: set() for p in performances}
        rng = random.Random(20260708)

        def create_booking(user, performance, seat_count):
            reserved = reserved_by_performance[performance.id]
            available = [
                seat for seat in performance.auditorium.seats.order_by("row", "number")
                if seat.id not in reserved
            ]
            if not available:
                return None
            rng.shuffle(available)
            seats = available[:seat_count]

            booking = Booking.objects.create(
                user=user,
                performance=performance,
            )
            total = 0
            for seat in seats:
                price = performance.zone_price(seat.auditorium_zone)
                BookingSeat.objects.create(
                    booking=booking,
                    performance=performance,
                    seat=seat,
                    price_at_purchase=price,
                )
                reserved.add(seat.id)
                total += price
            booking.total_price = total
            booking.save(update_fields=["total_price"])
            return booking

        # A few confirmed bookings for the original demo customer.
        for performance in performances[:3]:
            create_booking(customer_user, performance, seat_count=2)

        # Each additional client gets between 4 and 7 bookings on random performances.
        total_extra_bookings = 0
        for client in extra_customers:
            booking_count = rng.randint(4, 7)
            chosen_performances = rng.sample(performances, k=booking_count)
            for performance in chosen_performances:
                if create_booking(client, performance, seat_count=rng.randint(1, 3)):
                    total_extra_bookings += 1

        self.stdout.write(self.style.SUCCESS("Seed completato."))
        self.stdout.write(
            f"Teatri: {len(theaters)} • Spettacoli: {len(shows)} • Performance: {len(performances)} • "
            f"Prenotazioni clienti extra: {total_extra_bookings}"
        )
        self.stdout.write(
            "Utenti demo: admin/Admin123!, artista/Artist123!, artista2/Artist123!, "
            "gestore/Gestore123! (assegnato), gestore2/Gestore123! (nessun teatro), "
            "cliente/Cliente123!, cliente2..6/Cliente123! (4-7 prenotazioni ciascuno)"
        )
