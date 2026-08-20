from __future__ import annotations

from rest_framework.exceptions import ValidationError

from .models import ChecklistTemplate

# Which ChecklistTemplate (by key) applies to which machine/equipment code —
# see plan.md §12 and the PDF's 3 checklist tables. ISBM88 and ISBM110 share
# one template (the PDF prints them as two columns of the same checklist).
MACHINE_CODE_TO_TEMPLATE_KEY = {
    "ISBM88": "ISBM_88_110",
    "ISBM110": "ISBM_88_110",
    "INJ-CAPS": "INJECTION_1580",
}
EQUIPMENT_REFERENCE_TO_TEMPLATE_KEY = {
    "AC-88/110": "COMPRESSOR",
}


def resolve_template(machine=None, equipment=None) -> ChecklistTemplate:
    """Look up the checklist template for a machine or auxiliary equipment
    target. Raises ValidationError (not a lookup miss returning None) since
    the caller always has exactly one of machine/equipment and needs a
    template to proceed — there's nothing useful to do without one."""
    key = None
    if machine is not None:
        key = MACHINE_CODE_TO_TEMPLATE_KEY.get(machine.code)
    elif equipment is not None:
        key = EQUIPMENT_REFERENCE_TO_TEMPLATE_KEY.get(equipment.reference)

    if not key:
        target = machine.code if machine is not None else (equipment.reference if equipment is not None else "?")
        raise ValidationError(f"Aucun modèle de checklist préventive n'est défini pour '{target}'.")

    template = ChecklistTemplate.objects.filter(key=key, is_active=True).first()
    if not template:
        raise ValidationError(f"Modèle de checklist '{key}' introuvable ou inactif.")
    return template
