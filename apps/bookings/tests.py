"""Unit test per il flusso di prenotazione teatrale.

Sono implementate tre verifiche:

1. Prenotazioni duplicate: non e possibile prenotare piu volte lo stesso posto
   per la stessa performance.
2. Vietata cancellazione: non e possibile annullare una prenotazione se la
   performance associata e gia iniziata (o non e piu programmata).
3. Atomicita: la prenotazione di piu posti deve eseguire interamente oppure non
   eseguire affatto. Se anche un solo posto e gia occupato, l'intera operazione
   fallisce e nessun posto viene prenotato.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.shows.models import Category, Performance, PerformancePrice, Show
from apps.theaters.models import Auditorium, AuditoriumZone, Theater

from .models import Booking, BookingSeat


class BookingTestBase(TestCase):
    """Helper condivisi per costruire un teatro con posti e una performance."""

    def setUp(self):
        self.User = get_user_model()
        self.client_group = Group.objects.create(name="client")

    def make_client_user(self, username):
        user = self.User.objects.create_user(username=username, password="pass12345")
        user.groups.add(self.client_group)
        return user

    def make_performance(self, starts_at=None, status=Performance.STATUS_SCHEDULED):
        """Crea teatro, sala con una zona da 1 riga x 2 posti (A1, A2) e performance."""
        if starts_at is None:
            starts_at = timezone.now() + timedelta(days=1)

        theater = Theater.objects.create(
            name="Teatro Test",
            address="Via Roma 1",
            city="Roma",
        )
        auditorium = Auditorium.objects.create(theater=theater, name="Sala 1")
        zone = AuditoriumZone.objects.create(
            auditorium=auditorium, zone="Platea", rows=1, seats_per_row=2, order=1
        )
        auditorium.regenerate_seats()

        artist = self.User.objects.create_user(username="artista", password="pass12345")
        category = Category.objects.create(name="Prosa", slug="prosa")
        show = Show.objects.create(
            artist=artist,
            title="Spettacolo Test",
            description="Descrizione",
            category=category,
            duration_minutes=90,
        )
        performance = Performance.objects.create(
            show=show,
            auditorium=auditorium,
            starts_at=starts_at,
            status=status,
        )
        PerformancePrice.objects.create(
            performance=performance, auditorium_zone=zone, price=Decimal("20.00")
        )
        return performance

    def seat(self, performance, row, number):
        return performance.auditorium.seats.get(row=row, number=number)

    def make_confirmed_booking(self, user, performance, seats):
        """Crea una prenotazione confermata con i posti indicati."""
        booking = Booking.objects.create(user=user, performance=performance)
        total = Decimal("0.00")
        for seat in seats:
            price = performance.zone_price(seat.auditorium_zone)
            BookingSeat.objects.create(
                booking=booking,
                performance=performance,
                seat=seat,
                price_at_purchase=price,
            )
            total += price
        booking.total_price = total
        booking.save(update_fields=["total_price"])
        return booking


class DuplicateBookingTests(BookingTestBase):
    """Test di prenotazioni duplicate."""

    def test_stesso_posto_non_prenotabile_due_volte(self):
        performance = self.make_performance()
        user_a = self.make_client_user("cliente_a")
        user_b = self.make_client_user("cliente_b")
        a1 = self.seat(performance, "A", 1)

        # Prima prenotazione confermata sul posto A1.
        self.make_confirmed_booking(user_a, performance, [a1])

        # Un secondo tentativo sullo stesso (performance, seat) viola
        # unique_together e deve sollevare IntegrityError.
        booking_b = Booking.objects.create(user=user_b, performance=performance)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BookingSeat.objects.create(
                    booking=booking_b,
                    performance=performance,
                    seat=a1,
                    price_at_purchase=Decimal("20.00"),
                )


class BookingCancellationTests(BookingTestBase):
    """Test di vietata cancellazione di una prenotazione."""

    def test_non_cancellabile_se_performance_gia_iniziata(self):
        # La prenotazione nasce su una performance futura; poi la performance
        # inizia (starts_at spostato nel passato con un update diretto che
        # bypassa la validazione del modello). A quel punto non deve piu essere
        # annullabile.
        performance = self.make_performance()
        user = self.make_client_user("cliente")
        a1 = self.seat(performance, "A", 1)
        booking = self.make_confirmed_booking(user, performance, [a1])
        Performance.objects.filter(pk=performance.pk).update(
            starts_at=timezone.now() - timedelta(hours=1)
        )

        http_client = Client()
        http_client.force_login(user)
        http_client.post(reverse("bookings:booking_cancel", args=[booking.pk]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)
        self.assertEqual(booking.seats.count(), 1)

    def test_cancellabile_se_performance_futura(self):
        # Caso di controllo: una performance futura permette l'annullamento e
        # libera i posti (i BookingSeat vengono rimossi).
        performance = self.make_performance()
        user = self.make_client_user("cliente")
        a1 = self.seat(performance, "A", 1)
        booking = self.make_confirmed_booking(user, performance, [a1])

        http_client = Client()
        http_client.force_login(user)
        http_client.post(reverse("bookings:booking_cancel", args=[booking.pk]))

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.STATUS_CANCELLED)
        self.assertEqual(booking.seats.count(), 0)


class BookingAtomicityTests(BookingTestBase):
    """Test di atomicita sulla prenotazione dei posti."""

    def test_prenotazione_multipla_fallisce_interamente_su_conflitto(self):
        performance = self.make_performance()
        user_a = self.make_client_user("cliente_a")
        user_b = self.make_client_user("cliente_b")
        a1 = self.seat(performance, "A", 1)
        a2 = self.seat(performance, "A", 2)

        # L'utente A prenota A1.
        self.make_confirmed_booking(user_a, performance, [a1])

        # L'utente B tenta di prenotare A1 e A2 insieme: siccome A1 e occupato,
        # l'intera prenotazione deve fallire e nemmeno A2 deve risultare prenotato.
        http_client = Client()
        http_client.force_login(user_b)
        http_client.post(
            reverse("bookings:booking_create", args=[performance.pk]),
            data={"seats": [a1.pk, a2.pk]},
        )

        # B non deve avere alcuna prenotazione con posti confermati.
        self.assertFalse(
            BookingSeat.objects.filter(booking__user=user_b).exists()
        )
        # A2 deve restare libero: l'unico BookingSeat e quello di A su A1.
        self.assertFalse(
            BookingSeat.objects.filter(performance=performance, seat=a2).exists()
        )
        self.assertEqual(
            BookingSeat.objects.filter(performance=performance).count(), 1
        )
