from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Profile, Role
from apps.bookings.models import Booking, BookingSeat
from apps.shows.models import Category, Performance, PerformanceZonePrice, Show
from apps.theaters.models import (
    Hall,
    HallZone,
    Theater,
    TheaterAdmin,
    ZONE_BALCONATA,
    ZONE_CHOICES,
    ZONE_GALLERIA,
    ZONE_LOGGIONE,
    ZONE_PLATEA,
)

ZONE_MULTIPLIERS = {
    ZONE_PLATEA: Decimal("1.00"),
    ZONE_GALLERIA: Decimal("0.85"),
    ZONE_LOGGIONE: Decimal("0.70"),
    ZONE_BALCONATA: Decimal("0.75"),
}


class Command(BaseCommand):
    help = "Seed iniziale per ambiente di sviluppo."

    def handle(self, *args, **options):
        self.stdout.write("Avvio seed dati...")

        # Create roles
        role_admin, _ = Role.objects.get_or_create(name=Role.ROLE_ADMIN)
        role_artist, _ = Role.objects.get_or_create(name=Role.ROLE_ARTIST)
        role_manager, _ = Role.objects.get_or_create(name=Role.ROLE_MANAGER)
        role_client, _ = Role.objects.get_or_create(name=Role.ROLE_CLIENT)

        categories = ["Classico", "Commedia", "Drammatico", "Musical", "Moderno"]
        category_map = {}
        for name in categories:
            category, _ = Category.objects.get_or_create(
                name=name,
                defaults={"slug": slugify(name)},
            )
            category_map[name] = category

        User = get_user_model()

        def create_user(username, email, password, is_superuser=False, is_staff=False):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email},
            )
            if created:
                user.set_password(password)
                user.is_superuser = is_superuser
                user.is_staff = is_staff or is_superuser
                user.save()
            return user

        admin_user = create_user("admin", "admin@example.com", "Admin123!", is_superuser=True, is_staff=True)
        artist_user = create_user("artista", "artista@example.com", "Artist123!")
        manager_user = create_user("gestore", "gestore@example.com", "Gestore123!")
        customer_user = create_user("cliente", "cliente@example.com", "Cliente123!")

        def ensure_profile(user, role, city="", latitude=None, longitude=None, interests=None, display_name=""):
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = role
            profile.city = city
            profile.latitude = latitude
            profile.longitude = longitude
            profile.display_name = display_name
            profile.save()
            if interests is not None:
                profile.interests.set(interests)
            return profile

        ensure_profile(
            artist_user,
            role=role_artist,
            city="Roma",
            interests=[category_map["Commedia"], category_map["Drammatico"]],
            display_name="Artista Demo",
        )
        ensure_profile(
            customer_user,
            role=role_client,
            city="Milano",
            latitude=45.4642,
            longitude=9.1900,
            interests=[category_map["Musical"], category_map["Moderno"]],
            display_name="Cliente Demo",
        )
        ensure_profile(manager_user, role=role_manager, city="Milano", display_name="Gestore Demo")
        ensure_profile(admin_user, role=role_admin, city="Milano", display_name="Admin Demo")

        theater_centrale, _ = Theater.objects.get_or_create(
            name="Teatro Centrale",
            defaults={
                "description": "Teatro storico nel centro cittadino.",
                "address": "Via Roma 10",
                "city": "Milano",
                "province": "MI",
                "postal_code": "20121",
                "latitude": 45.4685,
                "longitude": 9.1824,
            },
        )
        theater_aurora, _ = Theater.objects.get_or_create(
            name="Teatro Aurora",
            defaults={
                "description": "Spazio moderno per eventi e musical.",
                "address": "Corso Torino 45",
                "city": "Torino",
                "province": "TO",
                "postal_code": "10121",
                "latitude": 45.0703,
                "longitude": 7.6869,
            },
        )

        hall_centrale, _ = Hall.objects.get_or_create(
            theater=theater_centrale,
            name="Sala A",
            defaults={"seat_rows": 8, "seat_cols": 10},
        )
        hall_aurora, _ = Hall.objects.get_or_create(
            theater=theater_aurora,
            name="Sala B",
            defaults={"seat_rows": 10, "seat_cols": 12},
        )

        HallZone.objects.get_or_create(
            hall=hall_centrale,
            zone=ZONE_PLATEA,
            defaults={"rows": 4, "seats_per_row": 10, "order": 1},
        )
        HallZone.objects.get_or_create(
            hall=hall_centrale,
            zone=ZONE_GALLERIA,
            defaults={"rows": 3, "seats_per_row": 8, "order": 2},
        )
        HallZone.objects.get_or_create(
            hall=hall_centrale,
            zone=ZONE_LOGGIONE,
            defaults={"rows": 2, "seats_per_row": 6, "order": 3},
        )

        HallZone.objects.get_or_create(
            hall=hall_aurora,
            zone=ZONE_PLATEA,
            defaults={"rows": 5, "seats_per_row": 12, "order": 1},
        )
        HallZone.objects.get_or_create(
            hall=hall_aurora,
            zone=ZONE_GALLERIA,
            defaults={"rows": 3, "seats_per_row": 10, "order": 2},
        )
        HallZone.objects.get_or_create(
            hall=hall_aurora,
            zone=ZONE_LOGGIONE,
            defaults={"rows": 2, "seats_per_row": 8, "order": 3},
        )

        Booking.objects.all().delete()

        hall_centrale.regenerate_seats()
        hall_aurora.regenerate_seats()

        TheaterAdmin.objects.get_or_create(theater=theater_centrale, user=manager_user)

        show_commedia, _ = Show.objects.get_or_create(
            title="La commedia degli errori",
            defaults={
                "description": "Una commedia brillante tra scambi di identita e ritmo serrato.",
                "category": category_map["Commedia"],
                "duration_minutes": 110,
                "created_by": artist_user,
                "status": Show.STATUS_APPROVED,
            },
        )
        show_commedia.artists.add(artist_user)

        show_musical, _ = Show.objects.get_or_create(
            title="Note di Mezzanotte",
            defaults={
                "description": "Musical contemporaneo con orchestra dal vivo.",
                "category": category_map["Musical"],
                "duration_minutes": 130,
                "created_by": artist_user,
                "status": Show.STATUS_APPROVED,
            },
        )
        show_musical.artists.add(artist_user)

        def future_datetime(days, hour, minute):
            base = timezone.localtime(timezone.now()).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            return base + timedelta(days=days)

        performance_one, _ = Performance.objects.get_or_create(
            show=show_commedia,
            theater=theater_centrale,
            hall=theater_centrale.halls.first(),
            starts_at=future_datetime(7, 20, 30),
            defaults={
                "base_price": 25.00,
                "status": Performance.STATUS_SCHEDULED,
                "created_by": manager_user,
            },
        )
        Performance.objects.get_or_create(
            show=show_musical,
            theater=theater_aurora,
            hall=theater_aurora.halls.first(),
            starts_at=future_datetime(10, 21, 0),
            defaults={
                "base_price": 30.00,
                "status": Performance.STATUS_SCHEDULED,
                "created_by": manager_user,
            },
        )

        booking, created = Booking.objects.get_or_create(
            user=customer_user,
            performance=performance_one,
            defaults={"status": Booking.STATUS_CONFIRMED},
        )

        for performance in Performance.objects.all():
            hall_zones = list(performance.hall.zones.values_list("zone", flat=True))
            zones = hall_zones or [zone for zone, _label in ZONE_CHOICES]
            base_price = Decimal(str(performance.base_price))
            for zone in zones:
                multiplier = ZONE_MULTIPLIERS.get(zone, Decimal("1.00"))
                price = (base_price * multiplier).quantize(Decimal("0.01"))
                PerformanceZonePrice.objects.get_or_create(
                    performance=performance,
                    zone=zone,
                    defaults={"price": price},
                )

        if created:
            reserved_ids = BookingSeat.objects.filter(
                performance=performance_one,
                booking__status=Booking.STATUS_CONFIRMED,
            ).values_list("seat_id", flat=True)
            available_seats = (
                performance_one.hall.seats.exclude(id__in=reserved_ids)
                .order_by("row", "number")
                .all()[:2]
            )
            total = 0
            for seat in available_seats:
                price = performance_one.zone_price(seat.zone)
                BookingSeat.objects.create(
                    booking=booking,
                    performance=performance_one,
                    seat=seat,
                    price_at_purchase=price,
                )
                total += price
            booking.total_price = total
            booking.save(update_fields=["total_price"])

        self.stdout.write(self.style.SUCCESS("Seed completato."))
        self.stdout.write(
            "Utenti demo (password iniziali): admin/Admin123!, artista/Artist123!, gestore/Gestore123!, cliente/Cliente123!"
        )
