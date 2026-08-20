from django.db import migrations

# Source: NOM MACHINES ET PROGRAMME MAINTENANCE.pdf / plan.md §3. Machine
# codes below already exist in the seeded DB (ISBM110/ISBM88/INJ-CAPS) —
# this migration only attaches child records, never creates/deletes Machine
# rows.
COMPONENTS = {
    "ISBM110": [
        ("Auto Loader", "AL-110"),
        ("Hopper Dryer", "HD-110"),
        ("Hot Runner", "HR-110-01"),
        ("Hot Runner", "HR-110-02"),
        ("Hot Runner", "HR-110-03"),
        ("Water Chiller", "WC-110"),
        ("Mixer", "MX-110"),
        ("Bottle packing machine", "BP-110"),
    ],
    "ISBM88": [
        ("Auto Loader", "AL-88"),
        ("Hopper Dryer", "HD-88"),
        ("Hot Runner", "HR-88-01"),
        ("Hot Runner", "HR-88-02"),
        ("Water Chiller", "WC-88"),
        ("Mixer", "MX-88"),
        ("Bottle packing machine", "BP-88"),
    ],
    "INJ-CAPS": [
        ("Auto Loader", "AL-1580"),
        ("Hopper Dryer", "HD-1580"),
        ("Water Chiller", "WC-1580"),
        ("Mixer", "MX-1580"),
        ("Water Tower", "WT-1580"),
        ("Material Crusher", "MC-1580"),
        ("Caps folding machine", "CF-1580"),
        ("Caps packing machine", "CP-1580"),
    ],
}

# machine_code -> number of blank-reference Mold rows to create (PDF leaves
# these blank on purpose; user configures the reference later in-app).
BLANK_MOLDS = {
    "ISBM110": 8,
    "ISBM88": 2,
}

# INJ-CAPS is the one line whose mold row has both a name and a reference
# in the source.
NAMED_MOLDS = {
    "INJ-CAPS": [("FLIP-TOP Mold", "FTC-1580")],
}

AUXILIARY_EQUIPMENT = [
    # name, reference, [machine codes it serves]
    ("Air compressor", "AC-88/110", ["ISBM88", "ISBM110"]),
    ("Air dryer", "AD-88/110", ["ISBM88", "ISBM110"]),
]


def seed(apps, schema_editor):
    Machine = apps.get_model("machines", "Machine")
    MachineComponent = apps.get_model("machines", "MachineComponent")
    Mold = apps.get_model("machines", "Mold")
    AuxiliaryEquipment = apps.get_model("machines", "AuxiliaryEquipment")

    machines_by_code = {}
    for code in list(COMPONENTS) + list(BLANK_MOLDS) + list(NAMED_MOLDS):
        m = Machine.objects.filter(code=code).first()
        if m:
            machines_by_code[code] = m

    for code, rows in COMPONENTS.items():
        machine = machines_by_code.get(code)
        if not machine:
            continue
        for name, reference in rows:
            MachineComponent.objects.get_or_create(machine=machine, name=name, reference=reference)

    for code, count in BLANK_MOLDS.items():
        machine = machines_by_code.get(code)
        if not machine:
            continue
        existing = Mold.objects.filter(machine=machine).count()
        # Idempotent per-machine, not per-row (blank rows are indistinguishable
        # from each other) — only top up if this migration hasn't run before.
        for _ in range(max(count - existing, 0)):
            Mold.objects.create(machine=machine, name="Mold", reference="")

    for code, rows in NAMED_MOLDS.items():
        machine = machines_by_code.get(code)
        if not machine:
            continue
        for name, reference in rows:
            Mold.objects.get_or_create(machine=machine, name=name, reference=reference)

    for name, reference, codes in AUXILIARY_EQUIPMENT:
        equipment, _ = AuxiliaryEquipment.objects.get_or_create(name=name, reference=reference)
        for code in codes:
            machine = machines_by_code.get(code)
            if machine:
                equipment.machines.add(machine)


def unseed(apps, schema_editor):
    MachineComponent = apps.get_model("machines", "MachineComponent")
    Mold = apps.get_model("machines", "Mold")
    AuxiliaryEquipment = apps.get_model("machines", "AuxiliaryEquipment")
    all_refs = [ref for rows in COMPONENTS.values() for _, ref in rows]
    MachineComponent.objects.filter(reference__in=all_refs).delete()
    Mold.objects.filter(name="Mold", reference="").delete()
    for rows in NAMED_MOLDS.values():
        for name, reference in rows:
            Mold.objects.filter(name=name, reference=reference).delete()
    for name, reference, _ in AUXILIARY_EQUIPMENT:
        AuxiliaryEquipment.objects.filter(name=name, reference=reference).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("machines", "0006_auxiliaryequipment_machinecomponent_mold"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
