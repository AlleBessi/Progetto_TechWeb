from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.shows.models import Category, Performance, PerformancePrice, Show
from apps.theaters.models import Auditorium, AuditoriumZone, Theater

from .models import Booking, BookingSeat

User = get_user_model()


class BookingTests(TestCase):
    def setUp(self):
        # ClientOnlyMixin fa passare nelle view di prenotazione solo gli
        # utenti che appartengono al gruppo "client" o "admin"; create_user()
        # da solo non assegna alcun gruppo (questo avviene solo all'interno
        # di RegisterView), quindi qui lo assegniamo manualmente.
        self.client_group = Group.objects.create(name="client")
        self.user1 = User.objects.create_user(username="utente1", password="password123")
        self.user1.groups.add(self.client_group)
        self.user2 = User.objects.create_user(username="utente2", password="password123")
        self.user2.groups.add(self.client_group)

        # Sala minima: un teatro, una zona, 2 posti (A1, A2)
        self.theater = Theater.objects.create(name="Teatro Test", address="Via Roma 1", city="Roma")
        self.auditorium = Auditorium.objects.create(theater=self.theater, name="Sala 1")
        self.zone = AuditoriumZone.objects.create(
            auditorium=self.auditorium, zone="Platea", rows=1, seats_per_row=2, order=1
        )
        self.auditorium.regenerate_seats()

        self.seat_a1 = self.auditorium.seats.get(row="A", number=1)
        self.seat_a2 = self.auditorium.seats.get(row="A", number=2)

        # Uno spettacolo con una performance programmata, che inizia domani
        self.artist = User.objects.create_user(username="artista", password="password123")
        self.category = Category.objects.create(name="Prosa", slug="prosa")
        self.show = Show.objects.create(
            artist=self.artist,
            title="Spettacolo Test",
            description="Descrizione",
            category=self.category,
            duration_minutes=90,
        )
        self.performance = Performance.objects.create(
            show=self.show,
            auditorium=self.auditorium,
            starts_at=timezone.now() + timedelta(days=1),
            status=Performance.STATUS_SCHEDULED,
        )
        PerformancePrice.objects.create(
            performance=self.performance, auditorium_zone=self.zone, price=Decimal("20.00")
        )

        self.client = Client()

    def test_duplicate_seat_reservation(self):
        # user1 prenota per primo il posto A1
        booking1 = Booking.objects.create(user=self.user1, performance=self.performance)
        BookingSeat.objects.create(
            booking=booking1, performance=self.performance, seat=self.seat_a1,
            price_at_purchase=Decimal("20.00"),
        )
        booking2 = Booking.objects.create(user=self.user2, performance=self.performance)

        # BookingSeat.clean() verifica se esiste gia' una prenotazione
        # confermata per la stessa coppia (performance, seat), quindi save()
        # deve sollevare ValidationError.
        duplicate_seat = BookingSeat(
            booking=booking2, performance=self.performance, seat=self.seat_a1,
            price_at_purchase=Decimal("20.00"),
        )
        with self.assertRaises(ValidationError):
            duplicate_seat.save()

    def test_cannot_cancel_booking(self):
        booking = Booking.objects.create(user=self.user1, performance=self.performance)
        BookingSeat.objects.create(
            booking=booking, performance=self.performance, seat=self.seat_a1,
            price_at_purchase=Decimal("20.00"),
        )

        # Booking.clean() rifiuterebbe una performance che inizia gia' nel
        # passato, quindi la spostiamo nel passato con un update() diretto,
        # che salta la validazione del modello e simula una performance gia'
        # iniziata.
        Performance.objects.filter(pk=self.performance.pk).update(
            starts_at=timezone.now() - timedelta(hours=2)
        )

        self.client.login(username="utente1", password="password123")
        url = reverse("bookings:booking_cancel", args=[booking.pk])
        response = self.client.post(url)

        # L'anullamento di una prenotazione per una performance gia' iniziata deve
        # essere rifiutato: la prenotazione resta confermata e il posto resta
        # riservato.
        self.assertRedirects(response, reverse("bookings:booking_list"))
        booking.refresh_from_db()
        self.assertTrue(BookingSeat.objects.filter(booking=booking, seat=self.seat_a1).exists())
        self.assertEqual(booking.status, Booking.STATUS_CONFIRMED)

    def test_book_seats_atomic(self):
        # user2 prenota il posto A1 prima che user1 provi a prenotare
        booking_user2 = Booking.objects.create(user=self.user2, performance=self.performance)
        BookingSeat.objects.create(
            booking=booking_user2, performance=self.performance, seat=self.seat_a2,
            price_at_purchase=Decimal("20.00"),
        )
        bookings_before = Booking.objects.count()

        # user1 prova a prenotare sia A1 che A2 in un'unica richiesta; A2 non
        # e' piu' libero, quindi l'intera richiesta deve essere rifiutata, non
        # solo A2.
        self.client.login(username="utente1", password="password123")
        url = reverse("bookings:booking_create", args=[self.performance.pk])
        response = self.client.post(url, {"seats": [self.seat_a1.pk, self.seat_a2.pk]})

        # La vista deve ritornare il codice HTTP 200 con un messaggio di errore, e non deve essere creata alcuna prenotazione.
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alcuni posti non sono più disponibili.")
        self.assertEqual(Booking.objects.count(), bookings_before)

        # A1 deve restare libero: un fallimento di un'operazione atomica non puo'
        # lasciarlo prenotato.
        seat_a1_taken = BookingSeat.objects.filter(
            performance=self.performance, seat=self.seat_a1
        ).exists()
        self.assertFalse(seat_a1_taken, "Il posto A1 doveva restare libero.")
