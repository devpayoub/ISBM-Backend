from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import StockItem, StockMovement


def apply_movement(item: StockItem, movement_type: str, delta, reason: str, user) -> StockMovement:
    """Single chokepoint for every stock quantity change — used by
    StockItemViewSet.move() directly, and by apps.package to auto-consume
    raw material/colorant when a bag is created. Never allows the
    resulting quantity to go negative."""
    quantity_before = item.quantity
    quantity_after = quantity_before + delta
    if quantity_after < 0:
        raise ValidationError(
            f"Stock insuffisant pour {item.name} ({item.reference}) : "
            f"{quantity_before} {item.unit} disponible, {abs(delta)} {item.unit} requis."
        )
    with transaction.atomic():
        item.quantity = quantity_after
        item.save(update_fields=["quantity", "updated_at"])
        movement = StockMovement.objects.create(
            stock_item=item, type=movement_type, delta=delta,
            quantity_before=quantity_before, quantity_after=quantity_after,
            reason=reason, created_by=user,
        )
    return movement
