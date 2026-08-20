from django.db import migrations

STEG_PARAMS = [
    # key, label, category
    ("STEG_ENABLED", "STEG activé", "steg"),
    ("STEG_TIME", "Heure STEG (optionnel)", "steg"),
    ("STEG_DATA", "Information STEG affichée (optionnel)", "steg"),
]


def seed_steg_parameters(apps, schema_editor):
    Parameter = apps.get_model("machines", "Parameter")
    from django.utils import timezone
    today = timezone.now().date()
    for key, label, category in STEG_PARAMS:
        # value=0 on STEG_ENABLED means OFF by default; is_active just marks
        # all three rows as live/available parameter definitions.
        Parameter.objects.get_or_create(
            key=key,
            defaults={
                "label": label, "value": 0, "text_value": "", "unit": "",
                "effective_from": today, "is_active": True,
                "category": category,
            },
        )


def remove_steg_parameters(apps, schema_editor):
    Parameter = apps.get_model("machines", "Parameter")
    Parameter.objects.filter(category="steg").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("machines", "0004_parameter_text_value_alter_parameter_value"),
    ]

    operations = [
        migrations.RunPython(seed_steg_parameters, remove_steg_parameters),
    ]
