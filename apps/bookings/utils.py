from collections import defaultdict

from apps.bookings.models import Booking, BookingSeat


def build_zone_layout(performance, reserved_ids, selected_ids=None):
    selected_ids = selected_ids or set()
    auditorium = performance.auditorium
    zone_defs = list(auditorium.zones.order_by("order", "id"))
    
    if not zone_defs:
        return []
    
    zone_order = [zone.id for zone in zone_defs]
    zone_labels = {zone.id: zone.zone for zone in zone_defs}
    zone_by_id = {zone.id: zone for zone in zone_defs}

    zone_rows = {zone: defaultdict(list) for zone in zone_order}
    seats = performance.auditorium.seats.select_related("auditorium_zone").all().order_by("row", "number")
    for seat in seats:
        zone_id = seat.auditorium_zone_id
        zone_rows.setdefault(zone_id, defaultdict(list))
        zone_rows[zone_id][seat.row].append(
            {
                "seat": seat,
                "zone": seat.auditorium_zone,
                "price": performance.zone_price(seat.auditorium_zone),
                "is_reserved": seat.id in reserved_ids,
                "is_selected": seat.id in selected_ids,
            }
        )

    zone_layout = []
    for index, zone in enumerate(zone_order, start=1):
        rows = zone_rows.get(zone)
        if not rows:
            continue
        zone_obj = zone_by_id.get(zone)
        if zone_obj is None:
            continue
        zone_layout.append(
            {
                "zone": zone_obj,
                "label": zone_labels.get(zone, zone),
                "price": performance.zone_price(zone_obj),
                "rows": sorted(rows.items()),
                "color_class": f"seat-zone-{index}",
            }
        )
    return zone_layout


def performance_rows(performances):
    rows = []
    for performance in performances:
        confirmed_booked = BookingSeat.objects.filter(
            performance=performance,
            booking__status=Booking.STATUS_CONFIRMED,
        ).count()
        total_seats = performance.auditorium.seats.count()
        occupancy = round((confirmed_booked / total_seats) * 100, 1) if total_seats else 0
        rows.append(
            {
                "performance": performance,
                "total_seats": total_seats,
                "booked_seats": confirmed_booked,
                "occupancy": occupancy,
            }
        )
    return rows


def calculate_occupancy(performance, zone_layout):
    zone_stats = []
    for zone_info in zone_layout:
        total = sum(len(seats) for _row, seats in zone_info["rows"])
        booked = BookingSeat.objects.filter(
            performance=performance,
            booking__status=Booking.STATUS_CONFIRMED,
            seat__auditorium_zone=zone_info["zone"],
        ).count()
        percentage = round((booked / total) * 100, 1) if total else 0
        zone_stats.append(
            {
                "label": zone_info["label"],
                "color_class": zone_info["color_class"],
                "total": total,
                "booked": booked,
                "percentage": percentage,
            }
        )
    global_total = sum(item["total"] for item in zone_stats)
    global_booked = sum(item["booked"] for item in zone_stats)
    global_percentage = round((global_booked / global_total) * 100, 1) if global_total else 0
    return {
        "zones": zone_stats,
        "global_total": global_total,
        "global_booked": global_booked,
        "global_percentage": global_percentage,
    }
